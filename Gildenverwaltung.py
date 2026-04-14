import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import re
import aiohttp
from datetime import datetime, timedelta

# --- KONFIGURATION (Bitte IDs anpassen!) ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
BOT_TOKEN = int(os.getenv('DISCORD_TOKEN') or 0)

CLASS_COLORS = {
    "Death Knight": 0xC41E3A, "Demon Hunter": 0xA330C9, "Druid": 0xFF7C0A,
    "Evoker": 0x33937F, "Hunter": 0xAAD372, "Mage": 0x3FC7EB,
    "Monk": 0x00FF98, "Paladin": 0xF48CBA, "Priest": 0xFFFFFF,
    "Rogue": 0xFFF468, "Shaman": 0x0070DD, "Warlock": 0x8788EE,
    "Warrior": 0xC69B6D
}

def get_raid_week_dates():
    now = datetime.now()
    days_until_thursday = (3 - now.weekday() + 7) % 7
    if days_until_thursday == 0:
        days_until_thursday = 7
    next_thursday = now + timedelta(days=days_until_thursday)
    following_wednesday = next_thursday + timedelta(days=6)
    return next_thursday.strftime("%d.%m."), following_wednesday.strftime("%d.%m.")

# --- RAID UMFRAGE ---
class RaidPollView(discord.ui.View):
    def __init__(self, week_range):
        super().__init__(timeout=None)
        self.week_range = week_range
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction: discord.Interaction, day_index: int):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_index]
        
        user_mention = interaction.user.mention
        # Extrahiere aktuelle Voter aus dem Feld
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

# --- FORUM AKTIONEN ---
class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_member")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prüfung auf Offizier
        if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Nur Offiziere können das tun!", ephemeral=True)

        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
                await interaction.response.send_message(f"✅ {member.mention} wurde aufgenommen!")
                # Optional: Thread schließen statt löschen für Archiv
                await interaction.channel.edit(archived=True, locked=True)
            except Exception as e:
                await interaction.response.send_message(f"Fehler: {e}", ephemeral=True)

class RegistrationModal(discord.ui.Modal, title='Mitglied Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder="https://raider.io/characters/eu/realm/name", required=True)
    discord_user = discord.ui.TextInput(label='Discord User (ID oder Erwähnung)', placeholder="ID oder @User", required=True)
    real_name = discord.ui.TextInput(label='Vorname', placeholder="z.B. Max", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Regex für Raider.io Link
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
        if not match:
            return await interaction.followup.send("❌ Ungültiger Raider.io Link!", ephemeral=True)
        
        realm, name = match.group(1), match.group(2)
        
        async with aiohttp.ClientSession() as session:
            url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await interaction.followup.send("❌ Charakter nicht gefunden!", ephemeral=True)
                data = await resp.json()

        char_name = data['name']
        char_class = data['class']
        char_spec = data.get('active_spec_name', 'Unbekannt')
        char_ilvl = data.get('gear', {}).get('item_level_equipped', 0)
        
        # Discord Member finden
        raw_id = "".join(filter(str.isdigit, self.discord_user.value))
        member = interaction.guild.get_member(int(raw_id)) if raw_id else None

        forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if not forum:
            return await interaction.followup.send("❌ Forum-Kanal nicht gefunden!", ephemeral=True)

        color = CLASS_COLORS.get(char_class, 0x3498db)
        embed = discord.Embed(title=f"Neuzugang: {char_name}", color=color)
        embed.add_field(name="Klasse / Spec", value=f"{char_class} ({char_spec})", inline=True)
        embed.add_field(name="Item-Level", value=str(char_ilvl), inline=True)
        embed.add_field(name="Spieler", value=f"{member.mention if member else 'Unbekannt'} / {self.real_name.value}", inline=False)
        embed.add_field(name="Links", value=f"🔗 [Rio]({self.rio_link.value}) | 📊 [Logs](https://www.warcraftlogs.com/character/eu/{realm}/{name})", inline=False)

        # Thread im Forum erstellen
        thread_bundle = await forum.create_thread(name=f"[{char_class}] {char_name} | {self.real_name.value}", embed=embed)
        
        if member:
            # Buttons in den Thread senden
            await thread_bundle.thread.send(f"💡 Offiziers-Optionen für {member.mention}:", view=ThreadActionView(member.id))
            try:
                # Automatisches Setzen von Nickname und Klassenrolle
                await member.edit(nick=f"{char_name} | {self.real_name.value}")
                c_role = discord.utils.get(interaction.guild.roles, name=char_class)
                if c_role: await member.add_roles(c_role)
            except:
                pass
        
        await interaction.followup.send(f"✅ Eintrag für {char_name} erstellt!", ephemeral=True)

# --- BOT SETUP ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        # Views registrieren für Persistenz nach Neustart
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
    """Erstellt das Haupt-Panel für Offiziere"""
    embed = discord.Embed(title="🏰 Gilden-Management Zentrale", description="Nutze den Button unten, um neue Mitglieder zu erfassen.", color=discord.Color.gold())
    await ctx.send(embed=embed, view=GildenLeitungView())

@bot.command()
async def raidumfrage(ctx):
    """Erstellt eine neue Raid-Umfrage"""
    if not any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
        return await ctx.send("❌ Keine Berechtigung.")
    
    start, end = get_raid_week_dates()
    view = RaidPollView(f"{start} - {end}")
    
    embed = discord.Embed(
        title=f"⚔️ Raid-Umfrage ({start} - {end})", 
        description="Bitte klickt auf die Tage, an denen ihr Zeit habt.",
        color=discord.Color.blue()
    )
    for d in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
        embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
    
    await ctx.send(embed=embed, view=view)

bot.run(BOT_TOKEN)
