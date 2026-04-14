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
    reason = discord.ui.TextInput(
        label='Grund für die Ablehnung', 
        style=discord.TextStyle.paragraph, 
        placeholder='Gear reicht nicht, Klasse voll, etc...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"❌ **Abgelehnt.**\n**Begründung:** {self.reason.value}")
        # Thread sperren und archivieren
        await interaction.channel.edit(locked=True, archived=True)

# --- VIEW FÜR BUTTONS IM THREAD ---
class ThreadActionView(discord.ui.View):
    def __init__(self, member_id, char_class):
        super().__init__(timeout=None)
        self.member_id = member_id
        self.char_class = char_class

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            if role:
                try:
                    await member.add_roles(role)
                    await interaction.response.send_message(f"✅ {member.mention} wurde aufgenommen! Thread wird gelöscht...")
                    await asyncio.sleep(5)
                    await interaction.channel.delete()
                except discord.Forbidden:
                    await interaction.response.send_message("❌ Fehler: Bot hat keine Rechte Rollen zu geben.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Fehler: Mitglied-Rolle nicht gefunden.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ User nicht mehr auf dem Server.", ephemeral=True)

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectModal())

# --- MODAL FÜR MITGLIEDER-REGISTRIERUNG ---
class MemberInfoModal(discord.ui.Modal, title='Mitglied Details'):
    def __init__(self, char_class, char_spec):
        super().__init__()
        self.char_class = char_class
        self.char_spec = char_spec

    discord_search = discord.ui.TextInput(label='Discord User (Name oder ID)')
    ingame_name = discord.ui.TextInput(label='Ingame Charakter Name', placeholder='z.B. Bolontíku')
    real_name = discord.ui.TextInput(label='Vorname')
    server_name = discord.ui.TextInput(label='Server', default=DEFAULT_SERVER_NAME)

    async def on_submit(self, interaction: discord.Interaction):
        # 1. User finden
        raw_input = self.discord_search.value.strip()
        user_id_str = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = None
        if user_id_str.isdigit():
            member = interaction.guild.get_member(int(user_id_str))
        if not member:
            member = discord.utils.get(interaction.guild.members, display_name=raw_input)
        if not member:
            member = discord.utils.get(interaction.guild.members, name=raw_input)

        # 2. Logs & Nickname Vorbereitung
        srv_slug = self.server_name.value.replace(" ", "-").lower()
        log_url = f"https://www.warcraftlogs.com/character/{REGION}/{srv_slug}/{self.ingame_name.value.lower()}"
        thread_name = f"[{self.char_class}] {self.ingame_name.value} ({self.char_spec}) {self.real_name.value}"
        
        # 3. Forum Thread erstellen
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        status_update = ""
        
        if forum_channel:
            # Thread erstellen
            result = await forum_channel.create_thread(
                name=thread_name,
                content=f"### 🛡️ Neuer Eintrag: {self.ingame_name.value}\n"
                        f"**Klasse:** {self.char_class} ({self.char_spec})\n"
                        f"**Vorname:** {self.real_name.value} | **Server:** {self.server_name.value}\n"
                        f"📈 [Warcraft Logs Profil]({log_url})"
            )
            
            # Buttons in den Thread posten (wenn User gefunden wurde)
            if member:
                view = ThreadActionView(member_id=member.id, char_class=self.char_class)
                await result.thread.send("💡 **Entscheidung treffen:**", view=view)

                # Nickname & Klassen-Rolle sofort anpassen
                try:
                    await member.edit(nick=f"{self.ingame_name.value} | {self.real_name.value}")
                    class_role = discord.utils.get(interaction.guild.roles, name=self.char_class)
                    if class_role:
                        await member.add_roles(class_role)
                    status_update = f"✅ Name & Klassen-Rolle für {member.mention} angepasst."
                except:
                    status_update = "⚠️ Nickname/Rolle konnte nicht automatisch geändert werden."
            else:
                status_update = "⚠️ Discord-User nicht gefunden (ID/Name prüfen)."

            await interaction.response.send_message(f"✅ Post erstellt!\n{status_update}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Forum-Kanal nicht gefunden!", ephemeral=True)

# --- KLASSEN/SPEC SELECTION ---
class SpecSelect(discord.ui.Select):
    def __init__(self, char_class):
        self.char_class = char_class
        options = [discord.SelectOption(label=s) for s in WOW_DATA[char_class]]
        super().__init__(placeholder="Spezialisierung wählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemberInfoModal(self.char_class, self.values[0]))
        await interaction.message.delete()

class GildenLeitungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Neues Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            view = discord.ui.View()
            options = [discord.SelectOption(label=cls) for cls in sorted(WOW_DATA.keys())]
            select = discord.ui.Select(placeholder="Klasse wählen...", options=options)
            
            async def class_callback(inter: discord.Interaction):
                spec_view = discord.ui.View()
                spec_view.add_item(SpecSelect(select.values[0]))
                await inter.response.send_message(f"Klasse: **{select.values[0]}**", view=spec_view)
            
            select.callback = class_callback
            view.add_item(select)
            await interaction.response.send_message("Wähle die Klasse:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

# --- BOT SETUP ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(GildenLeitungView())

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.channel.purge(limit=5, check=lambda m: m.author == bot.user)
    await ctx.send("### 🏰 Gildenverwaltung\nMitglieder registrieren & verwalten.", view=GildenLeitungView())
    await ctx.message.delete()

TOKEN = os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN_HIER'
bot.run(TOKEN)
