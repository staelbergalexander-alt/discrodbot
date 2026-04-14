import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os
import asyncio

# --- KONFIGURATION (Sicherer Abruf über Umgebungsvariablen) ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 1234567890)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 9876543210)
DEFAULT_SERVER_NAME = os.getenv('DEFAULT_SERVER') or "Blackhand"
REGION = "eu"

WOW_DATA = {
    "Death Knight": ["Blood", "Frost", "Unholy"],
    "Demon Hunter": ["Havoc", "Vengeance"],
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

class MemberInfoModal(discord.ui.Modal, title='Mitglied Details'):
    def __init__(self, char_class, char_spec):
        super().__init__()
        self.char_class = char_class
        self.char_spec = char_spec

    char_name = discord.ui.TextInput(label='Charakter Name', placeholder='Exakter Discord-Name des Users')
    server_name = discord.ui.TextInput(label='Server', default=DEFAULT_SERVER_NAME)
    real_name = discord.ui.TextInput(label='Vorname', placeholder='z.B. Rene')
    join_date = discord.ui.TextInput(label='Beitrittsdatum', default=datetime.now().strftime("%d.%m.%Y"))

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Daten vorbereiten
        srv_slug = self.server_name.value.replace(" ", "-").lower()
        log_url = f"https://www.warcraftlogs.com/character/{REGION}/{srv_slug}/{self.char_name.value.lower()}"
        thread_name = f"[{self.char_class}] {self.char_name.value} ({self.char_spec}) {self.real_name.value}"
        
        # 2. Forum Post erstellen
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            await forum_channel.create_thread(
                name=thread_name,
                content=f"## Neuer Eintrag: {self.char_name.value}\n"
                        f"**Server:** {self.server_name.value}\n**Klasse:** {self.char_class} ({self.char_spec})\n"
                        f"**Spieler:** {self.real_name.value}\n**Beigetreten:** {self.join_date.value}\n\n"
                        f"📈 [Warcraft Logs Profil]({log_url})"
            )

        # 3. User finden für Rolle & Nickname
        member = discord.utils.get(interaction.guild.members, display_name=self.char_name.value)
        # Falls er nicht über display_name gefunden wird, versuchen wir es über den Namen selbst
        if not member:
            member = discord.utils.get(interaction.guild.members, name=self.char_name.value)

        update_info = ""
        if member:
            # A) Nickname anpassen: "Charname (Vorname)"
            new_nick = f"{self.char_name.value} ({self.real_name.value})"
            try:
                await member.edit(nick=new_nick)
                update_info += f"✅ Nickname zu `{new_nick}` geändert.\n"
            except discord.Forbidden:
                update_info += "❌ Keine Rechte für Nickname-Änderung.\n"

            # B) Rolle vergeben
            role = discord.utils.get(interaction.guild.roles, name=self.char_class)
            if role:
                try:
                    await member.add_roles(role)
                    update_info += f"✅ Rolle `{self.char_class}` zugewiesen."
                except discord.Forbidden:
                    update_info += "❌ Keine Rechte für Rollenzuweisung."
        else:
            update_info = "⚠️ User nicht auf dem Discord gefunden (Name prüfen)."

        await interaction.response.send_message(f"✅ Eintrag erstellt!\n{update_info}", ephemeral=True)

class SpecSelect(discord.ui.Select):
    def __init__(self, char_class):
        self.char_class = char_class
        options = [discord.SelectOption(label=s) for s in WOW_DATA[char_class]]
        super().__init__(placeholder="Spezialisierung wählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemberInfoModal(self.char_class, self.values[0]))
        # Löscht das Auswahl-Menü im Kanal für die Sauberkeit
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
                await inter.response.send_message(f"Gewählte Klasse: **{select.values[0]}**", view=spec_view)
            
            select.callback = class_callback
            view.add_item(select)
            await interaction.response.send_message("Wähle die Klasse:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Du hast keine Berechtigung.", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True # WICHTIG für Nicknames & Rollen
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(GildenLeitungView())

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    # Kanal von alten Bot-Nachrichten säubern
    await ctx.channel.purge(limit=5, check=lambda m: m.author == bot.user)
    await ctx.send("### 🏰 Gildenverwaltung\nButton nutzen, um Mitglieder einzutragen.", view=GildenLeitungView())
    await ctx.message.delete()

TOKEN = os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN'
bot.run(TOKEN)
