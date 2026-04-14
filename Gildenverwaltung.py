import discord
from discord import app_commands
from discord.ext import commands
import os
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
REGION = "eu"

def get_raid_week_dates():
    now = datetime.now()
    days_until_thursday = (3 - now.weekday() + 7) % 7
    if days_until_thursday == 0: days_until_thursday = 7
    next_thursday = now + timedelta(days=days_until_thursday)
    following_wednesday = next_thursday + timedelta(days=6)
    return next_thursday.strftime("%d.%m."), following_wednesday.strftime("%d.%m.")

# --- RAID UMFRAGE ---
class RaidPollView(discord.ui.View):
    def __init__(self, week_range="Unbekannt"):
        super().__init__(timeout=None)
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction: discord.Interaction, day_index: int):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_index]
        user_mention = interaction.user.mention
        current_voters = field.value.split(", ") if field.value != "Keine Stimmen" else []
        
        if user_mention in current_voters:
            current_voters.remove(user_mention)
        else:
            current_voters.append(user_mention)
        
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

# --- REGISTRIERUNGS LOGIK ---

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            try:
                m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
                b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
                await interaction.response.send_message(f"✅ {member.mention} aufgenommen!")
                await asyncio.sleep(5); await interaction.channel.delete()
            except: await interaction.response.send_message("Rechte fehlen!", ephemeral=True)

class UserPickerView(discord.ui.View):
    """Dropdown zur Auswahl des Discord-Users"""
    def __init__(self, rio_link, real_name):
        super().__init__(timeout=180)
        self.rio_link = rio_link
        self.real_name = real_name

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Wähle den User aus...", min_values=1, max_values=1)
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        target_member = select.values[0]
        await interaction.response.defer(ephemeral=True)

        # API Abfrage
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.lower())
        if not match: return await interaction.followup.send("❌ Link ungültig!", ephemeral=True)
        
        srv, name = match.group(1), match.group(2)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=gear") as resp:
                if resp.status != 200: return await interaction.followup.send("❌ Charakter nicht gefunden!", ephemeral=True)
                data = await resp.json()

        forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum:
            char_class = data['class']
            char_name = data['name']
            
            # Thread erstellen
            res = await forum.create_thread(
                name=f"[{char_class}] {char_name} | {self.real_name}",
                content=f"### 🛡️ Neuer Eintrag: {char_name}\n**Klasse:** {char_class}\n**Spieler:** {self.real_name}\n• [Rio]({self.rio_link})"
            )
            
            # Rollen & Nickname
            try:
                await target_member.edit(nick=f"{char_name} | {self.real_name}")
                c_role = discord.utils.get(interaction.guild.roles, name=char_class)
                b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
                g_role = interaction.guild.get_role(GAST_ROLLE_ID)
                if c_role: await target_member.add_roles(c_role)
                if b_role: await target_member.add_roles(b_role)
                if g_role: await target_member.remove_roles(g_role)
                await res.thread.send(f"💡 Entscheidung für {target_member.mention}:", view=ThreadActionView(target_member.id))
            except: pass

        await interaction.followup.send(f"✅ Eintrag für {char_name} erstellt!", ephemeral=True)

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', required=True)
    real_name = discord.ui.TextInput(label='Vorname des Spielers', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Zeige Dropdown nach Modal-Abschluss
        view = UserPickerView(self.rio_link.value, self.real_name.value)
        await interaction.response.send_message("Wähle jetzt den Discord-User aus:", view=view, ephemeral=True)

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
    
    async def setup_hook(self):
        self.add_view(GildenLeitungView())
        self.add_view(RaidPollView())

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())

@bot.command()
async def raidumfrage(ctx):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in ctx.author.roles): return
    start, end = get_raid_week_dates()
    embed = discord.Embed(title=f"⚔️ Raid-Umfrage ({start} - {end})", color=discord.Color.blue())
    for d in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
        embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
    await ctx.send(embed=embed, view=RaidPollView())

bot.run(os.getenv('DISCORD_TOKEN'))
