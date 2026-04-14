import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import re
import aiohttp # WICHTIG: Für die API Abfrage

# --- KONFIGURATION (Über Umgebungsvariablen oder Standardwerte) ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID'))
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID'))
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID'))
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID'))
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID'))
MITGLIEDER_LISTE_KANAL_ID =  int(os.getenv('MITGLIEDER_LISTE_KANAL_ID'))
DEFAULT_SERVER_NAME = os.getenv('DEFAULT_SERVER') or "Blackhand"
REGION = "eu"

# --- MODALS & VIEWS (Logik wie gehabt) ---

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
                await asyncio.sleep(5); await interaction.channel.delete()
            except: await interaction.response.send_message("Rechte fehlen!", ephemeral=True)

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectModal(self.member_id))

# --- RAID UMFRAGE KOMPONENTE ---
class RaidPollView(discord.ui.View):
    def __init__(self, week_range="Unbekannt"):
        super().__init__(timeout=None)
        self.week_range = week_range
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction: discord.Interaction, day_index: int):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_index]
        user_mention = interaction.user.mention
        
        # Aktuelle Liste der Voter aus dem Embed-Feld holen
        current_voters = field.value.split(", ") if field.value != "Keine Stimmen" else []
        
        if user_mention in current_voters:
            current_voters.remove(user_mention)
        else:
            current_voters.append(user_mention)
        
        new_value = ", ".join(current_voters) if current_voters else "Keine Stimmen"
        count = len(current_voters)
        day_name = self.days_order[day_index]
        
        embed.set_field_at(day_index, name=f"{day_name} ({count})", value=new_value, inline=False)
        await interaction.response.edit_message(embed=embed)

    # Buttons mit festen Custom-IDs für Persistenz
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

# --- DAS SUPER-QUICK MODAL ---

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder='Link hier einfügen...', required=True)
    discord_search = discord.ui.TextInput(label='Discord User', placeholder='Discord ID oder Name', required=True)
    real_name = discord.ui.TextInput(label='Vorname des Spielers', placeholder='z.B. Alex', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Zeige dem User, dass der Bot arbeitet (API Abfrage kann 1-2 Sek dauern)
        await interaction.response.defer(ephemeral=True)

        # 1. Daten aus Link extrahieren
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
        if not match:
            return await interaction.followup.send("❌ Ungültiger Raider.io Link!", ephemeral=True)
        
        srv, name = match.group(1), match.group(2)
        api_url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=gear"

        # 2. Raider.io API abfragen
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    return await interaction.followup.send("❌ Charakter nicht auf Raider.io gefunden!", ephemeral=True)
                data = await response.json()

        # Daten von API
        char_name = data['name']
        char_server = data['realm']
        char_class = data['class']
        char_spec = data['active_spec_name'] or "Unbekannt"
        
        # 3. Discord User finden
        raw_input = self.discord_search.value.strip()
        user_id = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = interaction.guild.get_member(int(user_id)) if user_id.isdigit() else discord.utils.get(interaction.guild.members, display_name=raw_input)

        # 4. Links & Forum
        wcl_url = f"https://www.warcraftlogs.com/character/{REGION}/{srv}/{name}"
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        
        if forum_channel:
            res = await forum_channel.create_thread(
                name=f"[{char_class}] {char_name} | {self.real_name.value}",
                content=f"### 🛡️ Neuer Eintrag: {char_name}\n"
                        f"**Klasse:** {char_class} ({char_spec})\n"
                        f"**Spieler:** {self.real_name.value} | **Server:** {char_server}\n\n"
                        f"📈 **Profile:**\n• [Warcraft Logs]({wcl_url})\n• [Raider.io]({self.rio_link.value})"
            )

            # 5. Rollen & Nickname
            if member:
                await res.thread.send("💡 **Entscheidung treffen:**", view=ThreadActionView(member.id))
                try:
                    await member.edit(nick=f"{char_name} | {self.real_name.value}")
                    c_role = discord.utils.get(interaction.guild.roles, name=char_class)
                    b_role, g_role = interaction.guild.get_role(BEWERBER_ROLLE_ID), interaction.guild.get_role(GAST_ROLLE_ID)
                    
                    if g_role: await member.remove_roles(g_role)
                    if c_role: await member.add_roles(c_role)
                    if b_role: await member.add_roles(b_role)
                except: pass
            
            await interaction.followup.send(f"✅ Eintrag für **{char_name}** ({char_class}) erfolgreich erstellt!", ephemeral=True)

# --- BOT SETUP ---

class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            await interaction.response.send_modal(SuperQuickModal())
        else:
            await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default(); intents.message_content = True; intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self): self.add_view(GildenLeitungView())

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("### 🏰 Gildenverwaltung\nKlicke auf den Button, um ein Mitglied zu registrieren.", view=GildenLeitungView())

@bot.command()
async def raidumfrage(ctx):
    """Erstellt eine neue Raid-Umfrage für die kommende Woche"""
    if not any(role.id == OFFIZIER_ROLLE_ID for role in ctx.author.roles):
        return await ctx.send("❌ Keine Berechtigung.")
    
    start, end = get_raid_week_dates()
    embed = discord.Embed(
        title=f"⚔️ Raid-Umfrage ({start} - {end})",
        description="Bitte tragt eure Zeiten für die **nächste ID** ein.",
        color=discord.Color.blue()
    )
    for day in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
        embed.add_field(name=f"{day} (0)", value="Keine Stimmen", inline=False)
    
    await ctx.send(embed=embed, view=RaidPollView(f"{start} - {end}"))

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("### 🏰 Gildenverwaltung\nKlicke auf den Button, um ein Mitglied per Raider.io Link zu registrieren.", view=GildenLeitungView())

bot.run(os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN')
