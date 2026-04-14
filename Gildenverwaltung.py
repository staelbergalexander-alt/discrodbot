import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import re
import aiohttp
from datetime import datetime, timedelta

# --- KONFIGURATION ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)

CLASS_COLORS = {
    "Death Knight": 0xC41E3A, "Demon Hunter": 0xA330C9, "Druid": 0xFF7C0A,
    "Evoker": 0x33937F, "Hunter": 0xAAD372, "Mage": 0x3FC7EB,
    "Monk": 0x00FF98, "Paladin": 0xF48CBA, "Priest": 0xFFFFFF,
    "Rogue": 0xFFF468, "Shaman": 0x0070DD, "Warlock": 0x8788EE,
    "Warrior": 0xC69B6D
}

def get_raid_week_dates():
    """Berechnet den Zeitraum für die NÄCHSTE Raid-Woche (kommender Donnerstag bis Mittwoch)."""
    now = datetime.now()
    # Wochentage: Mo=0, Di=1, Mi=2, Do=3, Fr=4, Sa=5, So=6
    # Berechne Tage bis zum nächsten Donnerstag
    days_until_thursday = (3 - now.weekday() + 7) % 7
    
    # Wenn heute Donnerstag ist, planen wir für den Donnerstag in einer Woche
    if days_until_thursday == 0:
        days_until_thursday = 7
        
    next_thursday = now + timedelta(days=days_until_thursday)
    following_wednesday = next_thursday + timedelta(days=6)
    
    return next_thursday.strftime("%d.%m."), following_wednesday.strftime("%d.%m.")

# --- RAID UMFRAGE KOMPONENTE ---
class RaidPollView(discord.ui.View):
    def __init__(self, week_range):
        # Timeout=None sorgt dafür, dass die Buttons auch nach Tagen noch funktionieren
        super().__init__(timeout=None)
        self.week_range = week_range
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]
        self.votes = {day: [] for day in self.days_order}

    async def update_poll_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"⚔️ Raid-Umfrage für NÄCHSTE Woche ({self.week_range})",
            description="Wann habt ihr Zeit? (Planung für die kommende ID)",
            color=discord.Color.green()
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

    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="poll_do")
    async def v_do(self, i, b): await self.handle_vote(i, "Donnerstag")
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="poll_fr")
    async def v_fr(self, i, b): await self.handle_vote(i, "Freitag")
    @discord.ui.button(label="Sa", style=discord.ButtonStyle.gray, custom_id="poll_sa")
    async def v_sa(self, i, b): await self.handle_vote(i, "Samstag")
    @discord.ui.button(label="So", style=discord.ButtonStyle.gray, custom_id="poll_so")
    async def v_so(self, i, b): await self.handle_vote(i, "Sonntag")
    @discord.ui.button(label="Mo", style=discord.ButtonStyle.gray, custom_id="poll_mo")
    async def v_mo(self, i, b): await self.handle_vote(i, "Montag")
    @discord.ui.button(label="Di", style=discord.ButtonStyle.gray, custom_id="poll_di")
    async def v_di(self, i, b): await self.handle_vote(i, "Dienstag")
    @discord.ui.button(label="Mi", style=discord.ButtonStyle.gray, custom_id="poll_mi")
    async def v_mi(self, i, b): await self.handle_vote(i, "Mittwoch")

# --- REGISTRIERUNG & FORUM ---
class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_member")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
                await interaction.response.send_message(f"✅ {member.mention} ist jetzt Mitglied!")
                await asyncio.sleep(3)
                await interaction.channel.delete()
            except:
                await interaction.response.send_message("Fehler bei der Rollenzuweisung.", ephemeral=True)

class RegistrationModal(discord.ui.Modal, title='Mitglied Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', required=True)
    discord_user = discord.ui.TextInput(label='Discord User (ID oder Name)', required=True)
    real_name = discord.ui.TextInput(label='Vorname', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
        if not match:
            return await interaction.followup.send("❌ Ungültiger Link!", ephemeral=True)
        
        realm, name = match.group(1), match.group(2)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear") as resp:
                if resp.status != 200:
                    return await interaction.followup.send("❌ Charakter nicht gefunden!", ephemeral=True)
                data = await resp.json()

        char_name = data['name']
        char_class = data['class']
        char_spec = data.get('active_spec_name', 'Unbekannt')
        char_ilvl = data.get('gear', {}).get('item_level_equipped', 0)
        join_date = datetime.now().strftime("%d.%m.%Y")
        wcl_link = f"https://www.warcraftlogs.com/character/eu/{realm}/{name}"

        raw_id = self.discord_user.value.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = interaction.guild.get_member(int(raw_id)) if raw_id.isdigit() else None

        forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum:
            color = CLASS_COLORS.get(char_class, 0x3498db)
            embed = discord.Embed(title=f"Neuzugang: {char_name}", color=color)
            embed.add_field(name="Klasse / Spec", value=f"{char_class} ({char_spec})", inline=True)
            embed.add_field(name="Item-Level", value=str(char_ilvl), inline=True)
            embed.add_field(name="Spieler", value=f"{member.mention if member else 'Unbekannt'} / {self.real_name.value}", inline=False)
            embed.add_field(name="Eintritt", value=join_date, inline=True)
            embed.add_field(name="Links", value=f"🔗 [Rio]({self.rio_link.value}) | 📊 [Logs]({wcl_link})", inline=False)

            thread = await forum.create_thread(name=f"[{char_class}] {char_name} | {self.real_name.value}", embed=embed)
            if member:
                await thread.thread.send("💡 Offiziers-Aktion:", view=ThreadActionView(member.id))
                try:
                    await member.edit(nick=f"{char_name} | {self.real_name.value}")
                    c_role = discord.utils.get(interaction.guild.roles, name=char_class)
                    if c_role: await member.add_roles(c_role)
                except: pass
        
        await interaction.followup.send(f"✅ Eintrag für {char_name} erstellt!", ephemeral=True)

# --- BOT HAUPTKLASSE ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        # Statische Views registrieren für Beständigkeit nach Neustart
        self.add_view(GildenLeitungView())
        start, end = get_raid_week_dates()
        self.add_view(RaidPollView(f"{start} - {end}"))
        await self.tree.sync()

class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="btn_register")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            await interaction.response.send_modal(RegistrationModal())
        else:
            await interaction.response.send_message("Nur für Offiziere!", ephemeral=True)

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """Initiales Setup des Gilden-Panels"""
    await ctx.send("### 🏰 Gilden-Management Zentrale", view=GildenLeitungView())

@bot.command()
async def raidumfrage(ctx):
    """Erstellt eine neue Raid-Umfrage für die KOMMENDE Woche"""
    if not any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
        return await ctx.send("❌ Keine Berechtigung.")
    
    start, end = get_raid_week_dates()
    view = RaidPollView(f"{start} - {end}")
    
    embed = discord.Embed(
        title=f"⚔️ Raid-Umfrage ({start} - {end})", 
        description="Bitte tragt eure Zeiten für die **nächste ID** ein.",
        color=discord.Color.blue()
    )
    for d in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
        embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
    
    await ctx.send(embed=embed, view=view)

@bot.tree.command(name="update_entry", description="Aktualisiert einen Thread mit der richtigen Klassenfarbe")
@app_commands.describe(rio_link="Der Raider.io Link des Charakters")
async def update_entry(interaction: discord.Interaction, rio_link: str):
    if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
        return await interaction.response.send_message("❌ Keine Rechte!", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    match = re.search(r'characters/eu/([^/]+)/([^/]+)', rio_link.lower())
    if not match:
        return await interaction.followup.send("❌ Link-Format ungültig!", ephemeral=True)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={match.group(1)}&name={match.group(2)}&fields=gear") as resp:
            if resp.status != 200:
                return await interaction.followup.send("❌ Charakter nicht gefunden!", ephemeral=True)
            data = await resp.json()

    char_class = data['class']
    color = CLASS_COLORS.get(char_class, 0x3498db)
    
    embed = discord.Embed(title=f"Aktualisierter Eintrag: {data['name']}", color=color)
    embed.add_field(name="Klasse / Spec", value=f"{char_class} ({data.get('active_spec_name', '??')})", inline=True)
    embed.add_field(name="Item-Level", value=str(data.get('gear', {}).get('item_level_equipped', 0)), inline=True)
    embed.add_field(name="Link", value=f"🔗 [Rio]({rio_link})", inline=False)

    if isinstance(interaction.channel, discord.Thread):
        async for message in interaction.channel.history(oldest_first=True, limit=1):
            await message.edit(embed=embed)
            await interaction.followup.send("✅ Eintrag wurde gefärbt und aktualisiert!", ephemeral=True)
            return
    
    await interaction.followup.send("❌ Bitte führe den Befehl direkt im Forum-Thread aus!", ephemeral=True)

bot.run(os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN_HIER')
