import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import json
import asyncio
import re
import aiohttp
from datetime import datetime, timedelta, timezone

# --- KONFIGURATION (Railway Variablen) ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
RAID_READY_ROLLE_ID = int(os.getenv('RAID_READY_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID') or 0)
ARCHIV_CHANNEL_ID = int(os.getenv('ARCHIV_CHANNEL_ID') or 0)
SERVER_ID = int(os.getenv('SERVER_ID') or 0)

DB_FOLDER = "/app/data"
DB_FILE = os.path.join(DB_FOLDER, "mitglieder_db.json")
DASHBOARD_FILE = os.path.join(DB_FOLDER, "dashboard_config.json")

if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# --- DATENBANK FUNKTIONEN ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: 
            try: 
                data = json.load(f)
                updated = False
                for uid in list(data.keys()):
                    # Falls User noch altes Format hat (keine Liste 'chars')
                    if not isinstance(data[uid], dict) or "chars" not in data[uid]:
                        old_name = data[uid].get("name", "Unbekannt") if isinstance(data[uid], dict) else "Unbekannt"
                        old_realm = data[uid].get("realm", "Blackhand") if isinstance(data[uid], dict) else "Blackhand"
                        data[uid] = {"chars": [{"name": old_name, "realm": old_realm}]}
                        updated = True
                if updated: save_db(data)
                return data
            except: return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

def save_dashboard_id(msg_id, ch_id):
    with open(DASHBOARD_FILE, "w") as f: json.dump({"message_id": msg_id, "channel_id": ch_id}, f)

def load_dashboard_id():
    if os.path.exists(DASHBOARD_FILE):
        with open(DASHBOARD_FILE, "r") as f: return json.load(f)
    return None

# --- GEAR CHECK LOGIK ---
async def fetch_gear_data(session, realm, name):
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
    async with session.get(url) as resp:
        if resp.status != 200: return None
        data = await resp.json()
        items = data.get('gear', {}).get('items', {})
        return {
            "ilvl": data.get('gear', {}).get('item_level_equipped', 0),
            "missing_enchant": any(info.get('enchant') is None for slot, info in items.items() if slot in ['chest', 'legs', 'boots', 'mainhand', 'offhand', 'finger1', 'finger2']),
            "class": data.get('class', 'Unbekannt')
        }

# --- VIEWS ---
class DashboardView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Jetzt aktualisieren 🔄", style=discord.ButtonStyle.primary, custom_id="refresh_btn")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔄 Update läuft...", ephemeral=True)
        await interaction.client.update_dashboard_logic()

class RaidPollView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.days = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction, day_idx):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_idx]
        voters = field.value.split(", ") if field.value != "Keine Stimmen" else []
        if interaction.user.mention in voters: voters.remove(interaction.user.mention)
        else: voters.append(interaction.user.mention)
        embed.set_field_at(day_idx, name=f"{self.days[day_idx]} ({len(voters)})", value=", ".join(voters) if voters else "Keine Stimmen", inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="p0")
    async def b0(self, i, b): await self.handle_vote(i, 0)
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="p1")
    async def b1(self, i, b): await self.handle_vote(i, 1)
    @discord.ui.button(label="Sa", style=discord.ButtonStyle.gray, custom_id="p2")
    async def b2(self, i, b): await self.handle_vote(i, 2)
    @discord.ui.button(label="So", style=discord.ButtonStyle.gray, custom_id="p3")
    async def b3(self, i, b): await self.handle_vote(i, 3)
    @discord.ui.button(label="Mo", style=discord.ButtonStyle.gray, custom_id="p4")
    async def b4(self, i, b): await self.handle_vote(i, 4)
    @discord.ui.button(label="Di", style=discord.ButtonStyle.gray, custom_id="p5")
    async def b5(self, i, b): await self.handle_vote(i, 5)
    @discord.ui.button(label="Mi", style=discord.ButtonStyle.gray, custom_id="p6")
    async def b6(self, i, b): await self.handle_vote(i, 6)

# --- BOT KLASSE ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content, intents.members = True, True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(DashboardView())
        self.add_view(RaidPollView())
        self.archive_task.start()
        self.refresh_task.start()
        if SERVER_ID != 0:
            guild = discord.Object(id=SERVER_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    async def update_dashboard_logic(self):
        config = load_dashboard_id()
        if not config: return
        guild = self.get_guild(SERVER_ID)
        if not guild: return
        channel = guild.get_channel(config['channel_id'])
        if not channel: return
        try: message = await channel.fetch_message(config['message_id'])
        except: return

        db = load_db()
        min_ilvl = 265
        ready_list, not_ready_list = [], []

        async with aiohttp.ClientSession() as session:
            for uid, data in db.items():
                member = guild.get_member(int(uid))
                if not member: continue
                for char in data.get('chars', []):
                    res = await fetch_gear_data(session, char['realm'], char['name'])
                    if res:
                        is_ready = res['ilvl'] >= min_ilvl and not res['missing_enchant']
                        status = "✅" if is_ready else "⚠️"
                        line = f"{status} **{char['name']}** - iLvl: {res['ilvl']}"
                        if is_ready: ready_list.append(line)
                        else: not_ready_list.append(f"{line} (Gear/VZ fehlt)")
                    await asyncio.sleep(0.1)

        embed = discord.Embed(title="⚔️ RAID-READY DASHBOARD", color=discord.Color.gold())
        embed.description = f"Letztes Update: <t:{int(datetime.now().timestamp())}:R>"
        embed.add_field(name="🟢 BEREIT", value="\n".join(ready_list)[:1024] or "Niemand", inline=False)
        embed.add_field(name="🔴 NOCH ARBEIT", value="\n".join(not_ready_list)[:1024] or "Alles schick", inline=False)
        await message.edit(embed=embed, view=DashboardView())

    @tasks.loop(hours=6)
    async def archive_task(self):
        guild = self.get_guild(SERVER_ID)
        if not guild: return
        log_ch, arc_ch = guild.get_channel(LOG_CHANNEL_ID), guild.get_channel(ARCHIV_CHANNEL_ID)
        if log_ch and arc_ch:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
            async for msg in log_ch.history(limit=50):
                if msg.created_at < cutoff and "warcraftlogs.com" in msg.content:
                    await arc_ch.send(f"**Archiv:** {msg.content}")
                    await msg.delete()

    @tasks.loop(minutes=30)
    async def refresh_task(self):
        await self.update_dashboard_logic()

bot = GildenBot()

@bot.tree.command(name="setup_dashboard")
async def s_dash(interaction: discord.Interaction):
    if any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
        msg = await interaction.channel.send(embed=discord.Embed(title="Dashboard", description="Lade..."), view=DashboardView())
        save_dashboard_id(msg.id, interaction.channel_id)
        await interaction.response.send_message("✅ Dashboard aktiv!", ephemeral=True)
        await bot.update_dashboard_logic()

@bot.tree.command(name="add_char")
async def a_char(interaction: discord.Interaction, user: discord.Member, rio_link: str):
    match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
    if match:
        srv, name = match.group(1).capitalize(), match.group(2).capitalize()
        db = load_db()
        uid = str(user.id)
        if uid not in db: db[uid] = {"chars": []}
        # Prüfen ob Char schon da ist
        if any(c['name'] == name and c['realm'] == srv for c in db[uid]['chars']):
            return await interaction.response.send_message("Charakter ist bereits registriert!", ephemeral=True)
        
        db[uid]["chars"].append({"name": name, "realm": srv})
        save_db(db)
        await interaction.response.send_message(f"✅ {name}-{srv} für {user.display_name} hinzugefügt!")

bot.run(os.getenv('DISCORD_TOKEN'))
