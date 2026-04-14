import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import re
import aiohttp
from datetime import datetime, timedelta

# --- KONFIGURATION ---
# IDs als Umgebungsvariablen oder hier direkt eintragen
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)

# WoW Klassenfarben (Hex-Codes)
CLASS_COLORS = {
    "Death Knight": 0xC41E3A, "Demon Hunter": 0xA330C9, "Druid": 0xFF7C0A,
    "Evoker": 0x33937F, "Hunter": 0xAAD372, "Mage": 0x3FC7EB,
    "Monk": 0x00FF98, "Paladin": 0xF48CBA, "Priest": 0xFFFFFF,
    "Rogue": 0xFFF468, "Shaman": 0x0070DD, "Warlock": 0x8788EE,
    "Warrior": 0xC69B6D
}

def get_raid_week_dates():
    """Berechnet den Zeitraum von Donnerstag (Raid-Start) bis nächsten Mittwoch."""
    now = datetime.now()
    # Finde den letzten Donnerstag (Wochentag 3)
    days_since_thursday = (now.weekday() - 3) % 7
    last_thursday = now - timedelta(days=days_since_thursday)
    next_wednesday = last_thursday + timedelta(days=6)
    return last_thursday.strftime("%d.%m."), next_wednesday.strftime("%d.%m.")

# --- 1. RAID UMFRAGE LOGIK (START DONNERSTAG) ---
class RaidPollView(discord.ui.View):
    def __init__(self, week_range):
        super().__init__(timeout=None)
        self.week_range = week_range
        # Sortierung ab Donnerstag nach Weekly Reset
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]
        self.votes = {day: [] for day in self.days_order}

    async def update_poll_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"⚔️ Raid-Umfrage ({self.week_range})",
            description="Markiert alle Tage, an denen ihr Zeit habt!",
            color=discord.Color.blue()
        )
        for day in self.days_order:
            voters = self.votes[day]
            count = len(voters)
            voter_mentions = ", ".join([f"<@{v_id}>" for v_id in voters]) if voters else "Keine Stimmen"
            embed.add_field(name=f"{day} ({count})", value=voter_mentions, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_vote(self, interaction: discord.Interaction, day: str):
        user_id = interaction.user.id
        if user_id in self.votes[day]:
            self.votes[day].remove(user_id)
        else:
            self.votes[day].append(user_id)
        await self.update_poll_embed(interaction)

    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="p_do")
    async def v_do(self, i, b): await self.handle_vote(i, "Donnerstag")
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="p_fr")
    async def v_fr(self, i, b): await self.handle_vote(i, "Freitag")
    @discord.ui.button(label="Sa", style=discord.ButtonStyle.gray, custom_id="p_sa")
    async def v_sa(self, i, b): await self.handle_vote(i, "Samstag")
    @discord.ui.button(label="So", style=discord.ButtonStyle.gray, custom_id="p_so")
    async def v_so(self, i, b): await self.handle_vote(i, "Sonntag")
    @discord.ui.button(label="Mo", style=discord.ButtonStyle.gray, custom_id="p_mo")
    async def v_mo(self, i, b): await self.handle_vote(i, "Montag")
    @discord.ui.button(label="Di", style=discord.ButtonStyle.gray, custom_id="p_di")
    async def v_di(self, i, b): await self.handle_vote(i, "Dienstag")
    @discord.ui.button(label="Mi", style=discord.ButtonStyle.gray, custom_id="p_mi")
    async def v_mi(self, i, b): await self.handle_vote(i, "Mittwoch")

# --- 2. REGISTRIERUNG MIT SPEC, LOGS & EINTRITTSDATUM ---
class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="acc_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
                await interaction.response.send_message(f"✅ {member.mention} aufgenommen!")
                await asyncio.sleep(3); await interaction.channel.delete()
            except: await interaction.response.send_message("Rollenfehler!", ephemeral=True)

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder='https://raider.io/characters/eu/...', required=True)
    discord_search = discord.ui.TextInput(label='Discord User', placeholder='Name oder ID', required=True)
    real_name = discord.ui.TextInput(label='Vorname', placeholder='z.B. Alex', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
        if not match: return await interaction.followup.send("❌ Link-Format ungültig!", ephemeral=True)
        
        srv, name = match.group(1), match.group(2)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=gear") as resp:
                if resp.status != 200: return await interaction.followup.send("❌ Charakter nicht gefunden!", ephemeral=True)
                data = await resp.json()

        char_name, char_class = data['name'], data['class']
        char_spec = data.get('active_spec_name', 'Unbekannt')
        char_ilvl = data.get('gear', {}).get('item_level_equipped', 0)
        char_realm = data['realm']
        join_date = datetime.now().strftime("%d.%m.%Y")
        wcl_link = f"https://www.warcraftlogs.com/character/eu/{srv}/{name}"

        # Discord User auflösen
        raw_input = self.discord_search.value.strip()
        user_id = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = interaction.guild.get_member(int(user_id)) if user_id.isdigit() else discord.utils.get(interaction.guild.members, display_name=raw_input)

        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            color = CLASS_COLORS.get(char_class, 0x3498db)
            embed = discord.Embed(title=f"Neuer Eintrag: {char_name}", color=color)
            embed.add_field(name="Klasse / Spec", value=f"{char_class} ({char_spec})", inline=True)
            embed.add_field(name="Item-Level", value=str(char_ilvl), inline=True)
            embed.add_field(name="Spieler / Vorname", value=f"{member.mention if member else 'Unbekannt'} / {self.real_name.value}", inline=False)
            embed.add_field(name="Server / Eintritt", value=f"{char_realm} / {join_date}", inline=False)
            embed.add_field(name="Links", value=f"🔗 [Raider.io]({self.rio_link.value}) | 📊 [Warcraftlogs]({wcl_link})", inline=False)

            res = await forum_channel.create_thread(name=f"[{char_class}] {char_name} | {self.real_name.value}", embed=embed)
            if member:
                await res.thread.send("💡 Aktion wählen:", view=ThreadActionView(member.id))
                try:
                    await member.edit(nick=f"{char_name} | {self.real_name.value}")
                    c_role = discord.utils.get(interaction.guild.roles, name=char_class)
                    b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
                    if c_role: await member.add_roles(c_role)
                    if b_role: await member.add_roles(b_role)
                except: pass
        await interaction.followup.send(f"✅ Registriert: **{char_name}** ({char_spec})", ephemeral=True)

# --- 3. HAUPT PANEL & BOT SETUP ---
class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="main_add_btn")
    async def add(self, interaction: discord.Interaction, b):
        if any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            await interaction.response.send_modal(SuperQuickModal())
        else: await interaction.response.send_message("Keine Rechte!", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        self.add_view(GildenLeitungView())
        start, end = get_raid_week_dates()
        self.add_view(RaidPollView(f"{start} - {end}"))

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())

@bot.command(name="raidumfrage")
async def raidumfrage(ctx):
    if not any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
        return await ctx.send("❌ Nur für Offiziere.")
    start, end = get_raid_week_dates()
    view = RaidPollView(f"{start} - {end}")
    embed = discord.Embed(title=f"⚔️ Raid-Umfrage ({start} - {end})", color=discord.Color.blue())
    # Liste im Embed ab Donnerstag
    for d in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
        embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
    await ctx.send(embed=embed, view=view)
    @bot.tree.command(name="update_entry", description="Aktualisiert einen bestehenden Eintrag mit Farbe und neuen Daten")
@app_commands.describe(rio_link="Der Raider.io Link des Charakters")
async def update_entry(interaction: discord.Interaction, rio_link: str):
    if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
        return await interaction.response.send_message("❌ Keine Rechte!", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    
    # Daten von Raider.io holen (wie im Registrierungs-Modal)
    match = re.search(r'characters/eu/([^/]+)/([^/]+)', rio_link.lower())
    if not match: 
        return await interaction.followup.send("❌ Link-Format ungültig!", ephemeral=True)
    
    srv, name = match.group(1), match.group(2)
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=gear") as resp:
            if resp.status != 200: 
                return await interaction.followup.send("❌ Charakter nicht gefunden!", ephemeral=True)
            data = await resp.json()

    char_name = data['name']
    char_class = data['class']
    char_spec = data.get('active_spec_name', 'Unbekannt')
    char_ilvl = data.get('gear', {}).get('item_level_equipped', 0)
    color = CLASS_COLORS.get(char_class, 0x3498db)

    # Neues Embed erstellen
    embed = discord.Embed(title=f"Aktualisierter Eintrag: {char_name}", color=color)
    embed.add_field(name="Klasse / Spec", value=f"{char_class} ({char_spec})", inline=True)
    embed.add_field(name="Item-Level", value=str(char_ilvl), inline=True)
    embed.add_field(name="Links", value=f"🔗 [Raider.io]({rio_link})", inline=False)
    
    # Der Bot sucht die erste Nachricht im aktuellen Thread und bearbeitet sie
    if isinstance(interaction.channel, discord.Thread):
        async for message in interaction.channel.history(oldest_first=True, limit=1):
            await message.edit(embed=embed)
            await interaction.followup.send("✅ Thread-Farbe und Daten wurden aktualisiert!", ephemeral=True)
            return
    
    await interaction.followup.send("❌ Du musst diesen Befehl innerhalb des Threads ausführen, den du aktualisieren willst!", ephemeral=True)

bot.run(os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN_HIER')
