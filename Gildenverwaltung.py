import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os

# --- KONFIGURATION ---
OFFIZIER_ROLLE_ID = 123456789012345678 
FORUM_CHANNEL_ID = 987654321098765432 
DEFAULT_SERVER_NAME = "Blackhand" # Was standardmäßig im Feld stehen soll
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

    char_name = discord.ui.TextInput(label='Charakter Name', placeholder='z.B. Bolontíku')
    
    # NEU: Server-Feld mit Standardwert
    server_name = discord.ui.TextInput(
        label='Server', 
        default=DEFAULT_SERVER_NAME, 
        placeholder='z.B. Blackhand'
    )
    
    real_name = discord.ui.TextInput(label='Vorname', placeholder='z.B. Rene')
    
    join_date = discord.ui.TextInput(
        label='Beitrittsdatum', 
        default=datetime.now().strftime("%d.%m.%Y")
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Servername für URL formatieren (Leerzeichen zu Bindestrichen)
        srv_slug = self.server_name.value.replace(" ", "-").lower()
        name_slug = self.char_name.value.lower()
        
        # Warcraft Logs URL generieren
        log_url = f"https://www.warcraftlogs.com/character/{REGION}/{srv_slug}/{name_slug}"
        
        # Thread Name Format: [Klasse] Name (Spec) Vorname
        thread_name = f"[{self.char_class}] {self.char_name.value} ({self.char_spec}) {self.real_name.value}"
        
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        
        if forum_channel:
            await forum_channel.create_thread(
                name=thread_name,
                content=f"## Neuer Eintrag: {self.char_name.value}\n"
                        f"**Server:** {self.server_name.value}\n"
                        f"**Klasse:** {self.char_class}\n"
                        f"**Spec:** {self.char_spec}\n"
                        f"**Spieler:** {self.real_name.value}\n"
                        f"**Beigetreten am:** {self.join_date.value}\n\n"
                        f"📈 **Logs:** [Warcraft Logs Profil]({log_url})"
            )
            await interaction.response.send_message(f"✅ Eintrag für {self.char_name.value} erstellt!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Forum-Kanal nicht gefunden!", ephemeral=True)

class SpecSelect(discord.ui.Select):
    def __init__(self, char_class):
        self.char_class = char_class
        options = [discord.SelectOption(label=s) for s in WOW_DATA[char_class]]
        super().__init__(placeholder="Spezialisierung wählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemberInfoModal(self.char_class, self.values[0]))

class GildenLeitungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Neues Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_member_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            view = discord.ui.View()
            options = [discord.SelectOption(label=cls) for cls in sorted(WOW_DATA.keys())]
            select = discord.ui.Select(placeholder="Klasse wählen...", options=options)
            
            async def class_callback(inter: discord.Interaction):
                spec_view = discord.ui.View()
                spec_view.add_item(SpecSelect(select.values[0]))
                await inter.response.send_message(f"Klasse: {select.values[0]}", view=spec_view, ephemeral=True)
            
            select.callback = class_callback
            view.add_item(select)
            await interaction.response.send_message("Wähle die Klasse:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(GildenLeitungView())

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("### 🏰 Gildenverwaltung\nNutze den Button, um Foren-Einträge zu erstellen.", view=GildenLeitungView())

# Start
TOKEN = os.getenv('DISCORD_TOKEN') or 'DEIN_BOT_TOKEN_HIER'
bot.run(TOKEN)
