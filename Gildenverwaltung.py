import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import json
import asyncio
import re
import aiohttp
from datetime import datetime, timedelta

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
                for uid in data:
                    if "chars" not in data[uid]:
                        old_name = data[uid].get("name", "Unbekannt")
                        old_realm = data[uid].get("realm", "Blackhand")
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

def get_raid_week_dates():
    now = datetime.now()
    days_until_thursday = (3 - now.weekday() + 7) % 7
    if days_until_thursday == 0: days_until_thursday = 7
    next_thursday = now + timedelta(days=days_until_thursday)
    return next_thursday.strftime("%d.%m."), (next_thursday + timedelta(days=6)).strftime("%d.%m.")

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

# --- DASHBOARD UPDATE LOGIK ---
async def update_dashboard_logic(bot_instance):
    config = load_dashboard_id()
    if not config: return
    guild = bot_instance.get_guild(SERVER_ID)
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
                    line = f"{status} **{char['name']}** ({res['class']}) - iLvl: {res['ilvl']}"
                    if is_ready: ready_list.append(line)
                    else: not_ready_list.append(f"{line} (Gear/VZ fehlt)")
                await asyncio.sleep(0.1)

    embed = discord.Embed(title="⚔️ RAID-READY DASHBOARD", color=discord.Color.gold())
    embed.description = f"Letztes Update: <t:{int(datetime.now().timestamp())}:R>"
    if ready_list: embed.add_field(name="🟢 BEREIT", value="\n".join(ready_list)[:1024], inline=False)
    if not_ready_list: embed.add_field(name="🔴 NOCH ARBEIT", value="\n".join(not_ready_list)[:1024], inline=False)
    
    await message.edit(embed=embed, view=DashboardView())

# --- VIEWS ---
class DashboardView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Jetzt aktualisieren 🔄", style=discord.ButtonStyle.primary, custom_id="refresh_btn")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔄 Update läuft...", ephemeral=True)
        await update_dashboard_logic(interaction.client)

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

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="acc_btn")
    async def accept(self, interaction, button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role, b_role, g_role = interaction.guild.get_role(MITGLIED_ROLLE_ID), interaction.guild.get_role(BEWERBER_ROLLE_ID), interaction.guild.get_role(GAST_ROLLE_ID)
            if m_role: await member.add_roles(m_role)
            if b_role: await member.remove_roles(b_role)
            if g_role: await member.remove_roles(g_role)
            await interaction.response.send_message(f"✅ {member.mention} aufgenommen!")
            await asyncio.sleep(5)
            await interaction.channel.delete()

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="rej_btn")
    async def reject(self, interaction, button):
        await interaction.response.send_message("❌ Bewerbung abgelehnt.")

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', required=True)
    real_name = discord.ui.TextInput(label='Vorname', required=True)

    async def on_submit(self, interaction):
        await interaction.response.send_message("✅ Erwähne (@Name) jetzt den User!", ephemeral=True)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=60)
            uid = msg.content.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
            member = interaction.guild.get_member(int(uid))
            if member:
                match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
                if match:
                    srv, name = match.group(1).capitalize(), match.group(2).capitalize()
                    db = load_db()
                    db[str(member.id)] = {"chars": [{"name": name, "realm": srv}]}
                    save_db(db)
                    forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
                    if forum:
                        thread = await forum.create_thread(name=f"{name} | {self.real_name.value}", content=f"Neue Bewerbung: {self.rio_link.value}")
                        await thread.thread.send(f"Entscheidung für {member.mention}:", view=ThreadActionView(member.id))
                        await member.edit(nick=f"{name} | {self.real_name.value}")
            await msg.delete()
        except: await interaction.followup.send("Zeit abgelaufen oder Fehler.")

class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_mem")
    async def add(self, interaction, button):
        if any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles): await interaction.response.send_modal(SuperQuickModal())

# --- BOT KLASSE ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content, intents.members = True, True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(GildenLeitungView())
        self.add_view(DashboardView())
        self.add_view(RaidPollView())
        if not self.archive_task.is_running(): self.archive_task.start()
        if not self.refresh_task.is_running(): self.refresh_task.start()
        if SERVER_ID != 0:
            guild = discord.Object(id=SERVER_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

    @tasks.loop(hours=6)
    async def archive_task(self):
        guild = self.get_guild(SERVER_ID)
        log_ch, arc_ch = guild.get_channel(LOG_CHANNEL_ID), guild.get_channel(ARCHIV_CHANNEL_ID)
        if log_ch and arc_ch:
            cutoff = datetime.now(datetime.timezone.utc) - timedelta(hours=12)
            async for msg in log_ch.history(limit=50):
                if msg.created_at < cutoff and "warcraftlogs.com" in msg.content:
                    await arc_ch.send(f"**Archiv:** {msg.content}")
                    await msg.delete()

    @tasks.loop(minutes=30)
    async def refresh_task(self): await update_dashboard_logic(self)

    @archive_task.before_loop
    @refresh_task.before_loop
    async def before(self): await self.wait_until_ready()

bot = GildenBot()

@bot.tree.command(name="setup_dashboard")
async def s_dash(interaction):
    if any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
        msg = await interaction.channel.send(embed=discord.Embed(title="Dashboard", description="Lade..."), view=DashboardView())
        save_dashboard_id(msg.id, interaction.channel_id)
        await interaction.response.send_message("✅ Dashboard aktiv!", ephemeral=True)
        await update_dashboard_logic(bot)

@bot.command()
async def setup(ctx):
    if any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
        await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())

@bot.command()
async def raidumfrage(ctx):
    if any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
        s, e = get_raid_week_dates()
        embed = discord.Embed(title=f"⚔️ Raid-Umfrage ({s}-{e})", color=discord.Color.blue())
        for d in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
            embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
        await ctx.send(embed=embed, view=RaidPollView())

@bot.tree.command(name="add_char")
async def a_char(interaction, user: discord.Member, rio_link: str):
    match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
    if match:
        srv, name = match.group(1).capitalize(), match.group(2).capitalize()
        db = load_db()
        uid = str(user.id)
        if uid not in db: db[uid] = {"chars": []}
        db[uid]["chars"].append({"name": name, "realm": srv})
        save_db(db)
        await interaction.response.send_message(f"✅ {name} hinzugefügt!")

bot.run(os.getenv('DISCORD_TOKEN'))
