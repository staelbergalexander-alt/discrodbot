import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import re
import aiohttp
from datetime import datetime, timedelta

# --- KONFIGURATION ---
# IDs werden aus Umgebungsvariablen geladen oder auf 0 gesetzt
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)
MITGLIEDER_LISTE_KANAL_ID = int(os.getenv('MITGLIEDER_LISTE_KANAL_ID') or 0)
REGION = "eu"

# --- HILFSFUNKTION FÜR WEEKLY RESET ---
def get_raid_week_dates():
    """Berechnet den Zeitraum von diesem Mittwoch bis nächsten Dienstag."""
    now = datetime.now()
    # Wochentage: Mo=0, Di=1, Mi=2, Do=3, Fr=4, Sa=5, So=6
    # Wir wollen zum letzten Mittwoch zurück (Reset-Tag)
    days_since_wednesday = (now.weekday() - 2) % 7
    last_wednesday = now - timedelta(days=days_since_wednesday)
    next_tuesday = last_wednesday + timedelta(days=6)
    
    return last_wednesday.strftime("%d.%m."), next_tuesday.strftime("%d.%m.")

# --- 1. RAID UMFRAGE LOGIK ---
class RaidPollView(discord.ui.View):
    def __init__(self, week_range):
        super().__init__(timeout=None) # Buttons bleiben permanent aktiv
        self.week_range = week_range
        self.votes = {day: [] for day in ["Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag"]}

    async def update_poll_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"⚔️ Raid-Umfrage (Woche {self.week_range})",
            description="Wann passt es euch diese Raid-ID am besten? Klickt auf die Buttons!",
            color=discord.Color.blue()
        )
        for day, voters in self.votes.items():
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

    @discord.ui.button(label="Mi", style=discord.ButtonStyle.gray, custom_id="poll_mi")
    async def vote_mi(self, interaction, button): await self.handle_vote(interaction, "Mittwoch")
    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="poll_do")
    async def vote_do(self, interaction, button): await self.handle_vote(interaction, "Donnerstag")
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="poll_fr")
    async def vote_fr(self, interaction, button): await self.handle_vote(interaction, "Freitag")
    @discord.ui.button(label="Sa", style=discord.ButtonStyle.gray, custom_id="poll_sa")
    async def vote_sa(self, interaction, button): await self.handle_vote(interaction, "Samstag")
    @discord.ui.button(label="So", style=discord.ButtonStyle.gray, custom_id="poll_so")
    async def vote_so(self, interaction, button): await self.handle_vote(interaction, "Sonntag")
    @discord.ui.button(label="Mo", style=discord.ButtonStyle.gray, custom_id="poll_mo")
    async def vote_mo(self, interaction, button): await self.handle_vote(interaction, "Montag")
    @discord.ui.button(label="Di", style=discord.ButtonStyle.gray, custom_id="poll_di")
    async def vote_di(self, interaction, button): await self.handle_vote(interaction, "Dienstag")

# --- 2. REGISTRIERUNGS LOGIK (BEWERBUNGEN) ---
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
        await interaction.channel.edit(locked=True, archived=True)

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role, b_role = interaction.guild.get_role(MITGLIED_ROLLE_ID), interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
                await interaction.response.send_message(f"✅ {member.mention} aufgenommen!")
                await asyncio.sleep(3); await interaction.channel.delete()
            except: await interaction.response.send_message("Rechte fehlen!", ephemeral=True)

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectModal(self.member_id))

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder='Link einfügen...', required=True)
    discord_search = discord.ui.TextInput(label='Discord User', placeholder='ID oder Name', required=True)
    real_name = discord.ui.TextInput(label='Vorname', placeholder='z.B. Alex', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
        if not match: return await interaction.followup.send("❌ Ungültiger Link!", ephemeral=True)
        
        srv, name = match.group(1), match.group(2)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=gear") as resp:
                if resp.status != 200: return await interaction.followup.send("❌ Charakter nicht gefunden!", ephemeral=True)
                data = await resp.json()

        char_name, char_class = data['name'], data['class']
        raw_input = self.discord_search.value.strip()
        user_id = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = interaction.guild.get_member(int(user_id)) if user_id.isdigit() else discord.utils.get(interaction.guild.members, display_name=raw_input)

        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            res = await forum_channel.create_thread(
                name=f"[{char_class}] {char_name} | {self.real_name.value}",
                content=f"### 🛡️ Neuer Eintrag: {char_name}\n**Klasse:** {char_class}\n[Raider.io]({self.rio_link.value})"
            )
            if member:
                await res.thread.send("💡 Entscheidung treffen:", view=ThreadActionView(member.id))
                try:
                    await member.edit(nick=f"{char_name} | {self.real_name.value}")
                    c_role = discord.utils.get(interaction.guild.roles, name=char_class)
                    b_role, g_role = interaction.guild.get_role(BEWERBER_ROLLE_ID), interaction.guild.get_role(GAST_ROLLE_ID)
                    if g_role: await member.remove_roles(g_role)
                    if c_role: await member.add_roles(c_role)
                    if b_role: await member.add_roles(b_role)
                except: pass
        await interaction.followup.send(f"✅ Eintrag für **{char_name}** erstellt!", ephemeral=True)

# --- 3. BOT HAUPTKLASSE ---
class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_member_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            await interaction.response.send_modal(SuperQuickModal())
        else: await interaction.response.send_message("Keine Rechte!", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        # Registriert Views, damit Buttons nach Neustart funktionieren
        self.add_view(GildenLeitungView())
        # Hinweis: Bei Neustart wird die View ohne spezifisches Datum geladen,
        # da die Daten in der aktiven Instanz leben. Für persistente Speicherung
        # der Stimmen wäre eine Datenbank nötig.
        start, end = get_raid_week_dates()
        self.add_view(RaidPollView(f"{start} - {end}"))

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """Startet das Haupt-Panel"""
    await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())

@bot.command(name="raidumfrage")
async def raidumfrage(ctx):
    """Startet eine Raid-Tage Umfrage für die aktuelle WoW-Woche (Mi-Di)"""
    if not any(role.id == OFFIZIER_ROLLE_ID for role in ctx.author.roles):
        return await ctx.send("❌ Nur für Offiziere.")
    
    start, end = get_raid_week_dates()
    week_str = f"{start} - {end}"
    
    view = RaidPollView(week_str)
    embed = discord.Embed(
        title=f"⚔️ Raid-Umfrage (Woche {week_str})",
        description="Wann passt es euch diese Raid-ID am besten? Klickt auf die Buttons!",
        color=discord.Color.blue()
    )
    
    # Sortierung nach Raid-Woche: Beginnend mit Reset-Tag (Mittwoch)
    raid_days = ["Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag"]
    for day in raid_days:
        embed.add_field(name=f"{day} (0)", value="Keine Stimmen", inline=False)
    
    await ctx.send(embed=embed, view=view)

bot.run(os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN')
