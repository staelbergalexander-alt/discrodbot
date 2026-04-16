import discord
from discord import app_commands
from discord.ext import commands
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
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
DB_FILE = "mitglieder_db.json"
REGION = "eu"

# --- KONFIGURATION ---
DB_FOLDER = "/app/data" # Der Pfad zum Volume
DB_FILE = os.path.join(DB_FOLDER, "mitglieder_db.json")

# Erstelle den Ordner, falls er im Volume noch nicht existiert
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# Der Rest der Datenbank-Funktionen bleibt gleich:
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: 
            try: return json.load(f)
            except: return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f: 
        json.dump(data, f, indent=4)
        
def get_raid_week_dates():
    now = datetime.now()
    days_until_thursday = (3 - now.weekday() + 7) % 7
    if days_until_thursday == 0: days_until_thursday = 7
    next_thursday = now + timedelta(days=days_until_thursday)
    following_wednesday = next_thursday + timedelta(days=6)
    return next_thursday.strftime("%d.%m."), following_wednesday.strftime("%d.%m.")

# --- GEAR CHECK LOGIK ---
async def fetch_gear_data(session, realm, name):
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
    async with session.get(url) as resp:
        if resp.status != 200: return None
        data = await resp.json()
        items = data.get('gear', {}).get('items', {})
        ilvl = data.get('gear', {}).get('item_level_equipped', 0)
        
        missing_enchant = False
        empty_sockets = 0
        enchantable_slots = ['neck', 'back', 'chest', 'bracers', 'cloak', 'legs', 'boots', 'mainhand', 'offhand', 'finger1', 'finger2']
        
        for slot, info in items.items():
            if slot in enchantable_slots and info.get('enchant') is None:
                missing_enchant = True
            empty_sockets += info.get('gems_missing', 0)
            
        return {
            "ilvl": ilvl,
            "missing_enchant": missing_enchant,
            "empty_sockets": empty_sockets
        }

# --- VIEWS ---
class RaidPollView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction: discord.Interaction, day_index: int):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_index]
        user_mention = interaction.user.mention
        current_voters = field.value.split(", ") if field.value != "Keine Stimmen" else []
        
        if user_mention in current_voters: current_voters.remove(user_mention)
        else: current_voters.append(user_mention)
        
        new_value = ", ".join(current_voters) if current_voters else "Keine Stimmen"
        embed.set_field_at(day_index, name=f"{self.days_order[day_index]} ({len(current_voters)})", value=new_value, inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="poll_0")
    async def v_0(self, i, b): await self.handle_vote(i, 0)
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="poll_1")
    async def v_1(self, i, b): await self.handle_vote(i, 1)
    @discord.ui.button(label="Sa", style=discord.ButtonStyle.gray, custom_id="poll_2")
    async def v_2(self, i, b): await self.handle_vote(i, 2)
    @discord.ui.button(label="So", style=discord.ButtonStyle.gray, custom_id="poll_3")
    async def v_3(self, i, b): await self.handle_vote(i, 3)
    @discord.ui.button(label="Mo", style=discord.ButtonStyle.gray, custom_id="poll_4")
    async def v_4(self, i, b): await self.handle_vote(i, 4)
    @discord.ui.button(label="Di", style=discord.ButtonStyle.gray, custom_id="poll_5")
    async def v_5(self, i, b): await self.handle_vote(i, 5)
    @discord.ui.button(label="Mi", style=discord.ButtonStyle.gray, custom_id="poll_6")
    async def v_6(self, i, b): await self.handle_vote(i, 6)

class RejectModal(discord.ui.Modal, title='Ablehnung begründen'):
    reason = discord.ui.TextInput(label='Grund', style=discord.TextStyle.paragraph, required=True)
    def __init__(self, member_id):
        super().__init__()
        self.member_id = member_id

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.member_id)
        if member:
            b_role, g_role = interaction.guild.get_role(BEWERBER_ROLLE_ID), interaction.guild.get_role(GAST_ROLLE_ID)
            try:
                if b_role: await member.remove_roles(b_role)
                if g_role: await member.add_roles(g_role)
            except: pass
        await interaction.response.send_message(f"❌ Abgelehnt. Grund: {self.reason.value}")
        await asyncio.sleep(3)
        await interaction.channel.edit(locked=True, archived=True)

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            try:
                m_role, b_role = interaction.guild.get_role(MITGLIED_ROLLE_ID), interaction.guild.get_role(BEWERBER_ROLLE_ID)
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
                await interaction.response.send_message(f"✅ {member.mention} aufgenommen!")
                await asyncio.sleep(5)
                await interaction.channel.delete()
            except: await interaction.response.send_message("Rechte fehlen!", ephemeral=True)
                
    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectModal(self.member_id))

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', required=True)
    real_name = discord.ui.TextInput(label='Vorname des Spielers', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Daten empfangen! Erwähne (@Name) jetzt den User.", ephemeral=True)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=60.0)
            raw_id = msg.content.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
            target_member = interaction.guild.get_member(int(raw_id)) if raw_id.isdigit() else None
            
            if not target_member: return await interaction.followup.send("❌ User nicht gefunden.", ephemeral=True)
            match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
            if not match: return await interaction.followup.send("❌ Link ungültig!", ephemeral=True)
                
            db = load_db()
            db[str(target_member.id)] = {"name": name, "realm": srv}
            save_db(db)
            
            api_url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=gear"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200: return await interaction.followup.send("❌ Char nicht gefunden!", ephemeral=True)
                    data = await resp.json()

            char_class, char_name = data['class'], data['name']
            forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
            if forum:
                res = await forum.create_thread(
                    name=f"[{char_class}] {char_name} | {self.real_name.value}",
                    content=f"### 🛡️ Neuer Eintrag: {char_name}\n**Klasse:** {char_class}\n**Spieler:** {self.real_name.value}\n[Raider.io]({self.rio_link.value})"
                )
                await res.thread.send(f"💡 Entscheidung für {target_member.mention}:", view=ThreadActionView(target_member.id))
                await target_member.edit(nick=f"{char_name} | {self.real_name.value}")
            await msg.delete()
        except Exception as e: await interaction.followup.send(f"Fehler: {e}", ephemeral=True)

class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            await interaction.response.send_modal(SuperQuickModal())
        else: await interaction.response.send_message("Keine Rechte!", ephemeral=True)

# --- BOT KLASSE ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        self.add_view(GildenLeitungView())
        self.add_view(RaidPollView())
        if SERVER_ID != 0:
            MY_GUILD = discord.Object(id=SERVER_ID)
            self.tree.copy_global_to(guild=MY_GUILD)
            await self.tree.sync(guild=MY_GUILD)

bot = GildenBot()

# --- BEFEHLE ---
@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync(guild=discord.Object(id=SERVER_ID))
    await ctx.send("✅ Slash-Commands synchronisiert!")

@bot.command()
async def setup(ctx):
    if any(role.id == OFFIZIER_ROLLE_ID for role in ctx.author.roles):
        await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())

@bot.command()
async def raidumfrage(ctx):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in ctx.author.roles): return
    start, end = get_raid_week_dates()
    embed = discord.Embed(title=f"⚔️ Raid-Umfrage ({start} - {end})", color=discord.Color.blue())
    for d in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
        embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
    await ctx.send(embed=embed, view=RaidPollView())

@bot.tree.command(name="add_member_rio", description="Füge ein Mitglied per Raider.io Link hinzu")
async def add_member_rio(interaction: discord.Interaction, user: discord.Member, rio_link: str):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("❌ Keine Rechte!", ephemeral=True)
    match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
    if not match: return await interaction.response.send_message("❌ Ungültiger Link!", ephemeral=True)
    
    server, charname = match.group(1).capitalize(), match.group(2).capitalize()
    db = load_db()
    db[str(user.id)] = {"name": charname, "realm": server}
    save_db(db)
    await interaction.response.send_message(f"✅ Verknüpft: {user.mention} ↔️ **{charname}** ({server})")

@bot.tree.command(name="list_members", description="Zeigt alle registrierten Mitglieder")
async def list_members(interaction: discord.Interaction):
    db = load_db()
    if not db: return await interaction.response.send_message("Die Liste ist leer.", ephemeral=True)
    liste = [f"• <@{uid}>: **{info['name']}** ({info['realm']})" for uid, info in db.items()]
    await interaction.response.send_message(embed=discord.Embed(title="Mitglieder", description="\n".join(liste), color=discord.Color.gold()))

@bot.tree.command(name="check_raid_ready", description="Prüft Itemlevel, VZ und Gems")
async def check_raid_ready(interaction: discord.Interaction, min_ilvl: int = 270):
    await interaction.response.defer()
    db = load_db()
    ready, not_ready, missing = [], [], []

    async with aiohttp.ClientSession() as session:
        for user_id, info in db.items():
            res = await fetch_gear_data(session, info['realm'], info['name'])
            if res:
                warnings = []
                if res['missing_enchant']: warnings.append("✨ VZ fehlt")
                if res['empty_sockets'] > 0: warnings.append(f"💎 {res['empty_sockets']} Gems")
                
                warn_text = f" ({', '.join(warnings)})" if warnings else ""
                line = f"<@{user_id}>: **{res['ilvl']}**{warn_text}"
                
                if res['ilvl'] >= min_ilvl and not warnings: ready.append(f"✅ {line}")
                else: not_ready.append(f"⚠️ {line}" if res['ilvl'] >= min_ilvl else f"❌ {line}")
            else:
                missing.append(f"<@{user_id}> ({info['name']}?)")
            await asyncio.sleep(0.1)

    embed = discord.Embed(title=f"🛡️ Raid-Ready Check (Min: {min_ilvl})", color=discord.Color.blue())
    embed.add_field(name="✅ Ready", value="\n".join(ready) or "Niemand", inline=False)
    embed.add_field(name="❌ Baustellen", value="\n".join(not_ready) or "Niemand", inline=False)
    if missing: embed.add_field(name="⚠️ Fehler", value="\n".join(missing), inline=False)
    await interaction.followup.send(embed=embed)

bot.run(os.getenv('DISCORD_TOKEN'))
