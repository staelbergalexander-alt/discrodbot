import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os
import asyncio

# --- KONFIGURATION (Über Umgebungsvariablen oder Standardwerte) ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID'))
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID'))
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID'))
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID'))
DEFAULT_SERVER_NAME = os.getenv('DEFAULT_SERVER') or "Blackhand"
REGION = "eu"

WOW_DATA = {
    "Death Knight": ["Blood", "Frost", "Unholy"],
    "Demon Hunter": ["Havoc", "Vengeance", "Devourer"],
    "Druid": ["Balance", "Feral", "Guardian", "Restoration"],
    "Evoker": ["Devastation", "Preservation", "Augmentation"],
    "Hunter": ["Beast Mastery", "Marksmanship", "Survival"],
    "Mage": ["Arcane", "Fire", "Frost"],
    "Monk": ["Brewmaster", "Mistweaver", "Windwalker"],
    "Paladin": ["Holy", "Protection", "Retribution"],
    "Priest": ["Discipline", "Holy", "Shadow"],
    "Rogue": ["Assassination", "Outlaw", "Subtlety"],
    "Shaman": ["Elemental", "Enhancement", "Restoration"],
    "Warlock": ["Affliction", "Demonology", "Destruction"],
    "Warrior": ["Arms", "Fury", "Protection"]
}
# --- MODAL FÜR ABLEHNUNG ---
class RejectModal(discord.ui.Modal, title='Ablehnung begründen'):
    reason = discord.ui.TextInput(label='Grund', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"❌ **Abgelehnt.**\n**Begründung:** {self.reason.value}")
        await interaction.channel.edit(locked=True, archived=True)

# --- VIEW FÜR BUTTONS IM THREAD ---
class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role) # Bewerber-Rolle entfernen
                await interaction.response.send_message(f"✅ {member.mention} aufgenommen! Bewerber-Status entfernt.")
                await asyncio.sleep(5)
                await interaction.channel.delete()
            except:
                await interaction.response.send_message("❌ Fehler bei Rollenvergabe.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ User nicht gefunden.", ephemeral=True)

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            if b_role: 
                try: await member.remove_roles(b_role) # Bewerber-Rolle auch bei Ablehnung weg
                except: pass
        await interaction.response.send_modal(RejectModal())

# --- HAUPT-MODAL (DATEN-EINGABE) ---
class MemberInfoModal(discord.ui.Modal, title='Mitglied Details'):
    def __init__(self, char_class, char_spec):
        super().__init__()
        self.char_class = char_class
        self.char_spec = char_spec

    discord_search = discord.ui.TextInput(label='Discord User (Name oder ID)'placeholder='Discord ID')
    ingame_name = discord.ui.TextInput(label='Ingame Charakter Name')
    real_name = discord.ui.TextInput(label='Vorname')
    server_name = discord.ui.TextInput(label='Server', default=DEFAULT_SERVER_NAME)

    async def on_submit(self, interaction: discord.Interaction):
        # 1. User finden
        raw_input = self.discord_search.value.strip()
        user_id_str = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = None
        if user_id_str.isdigit(): member = interaction.guild.get_member(int(user_id_str))
        if not member: member = discord.utils.get(interaction.guild.members, display_name=raw_input)
        if not member: member = discord.utils.get(interaction.guild.members, name=raw_input)

        # 2. Forum Thread erstellen
        srv_slug = self.server_name.value.replace(" ", "-").lower()
        log_url = f"https://www.warcraftlogs.com/character/{REGION}/{srv_slug}/{self.ingame_name.value.lower()}"
        thread_name = f"[{self.char_class}] {self.ingame_name.value} ({self.char_spec})"
        
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            res = await forum_channel.create_thread(
                name=thread_name,
                content=f"### 🛡️ Neuer Eintrag: {self.ingame_name.value}\n**Klasse:** {self.char_class} ({self.char_spec})\n**Spieler:** {self.real_name.value}\n📈 [Logs]({log_url})"
            )
            
            # 3. Rollen & Nickname (Bewerber-Status setzen)
            status = ""
            if member:
                view = ThreadActionView(member_id=member.id)
                await res.thread.send("💡 **Entscheidung treffen:**", view=view)
                try:
                    await member.edit(nick=f"{self.ingame_name.value} | {self.real_name.value}")
                    c_role = discord.utils.get(interaction.guild.roles, name=self.char_class)
                    b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
                    if c_role: await member.add_roles(c_role)
                    if b_role: await member.add_roles(b_role) # Hier bekommt er die Bewerber-Rolle
                    status = f"✅ Setup für {member.mention} abgeschlossen."
                except: status = "⚠️ Rollen-Update fehlgeschlagen."
            else: status = "⚠️ User nicht gefunden."

            await interaction.response.send_message(f"Eintrag erstellt!\n{status}", ephemeral=True)

# --- KLASSEN WAHL ---
class SpecSelect(discord.ui.Select):
    def __init__(self, char_class):
        self.char_class = char_class
        options = [discord.SelectOption(label=s) for s in WOW_DATA[char_class]]
        super().__init__(placeholder="Spezialisierung wählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemberInfoModal(self.char_class, self.values[0]))
        await interaction.message.delete()

class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Neues Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            view = discord.ui.View()
            options = [discord.SelectOption(label=cls) for cls in sorted(WOW_DATA.keys())]
            select = discord.ui.Select(placeholder="Klasse wählen...", options=options)
            async def class_callback(inter: discord.Interaction):
                v = discord.ui.View(); v.add_item(SpecSelect(select.values[0]))
                await inter.response.send_message(f"Klasse: {select.values[0]}", view=v)
            select.callback = class_callback
            view.add_item(select)
            await interaction.response.send_message("Wähle die Klasse:", view=view, ephemeral=True)

# --- BOT START ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self): self.add_view(GildenLeitungView())

bot = GildenBot()
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.channel.purge(limit=5, check=lambda m: m.author == bot.user)
    await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())
    await ctx.message.delete()

bot.run(os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN')
