import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

# --- KONFIGURATION ---
OFFIZIER_ROLLE_ID = 1480564049191370763 
FORUM_CHANNEL_ID = 1492325655101313074 # Die ID deines FORUM-Kanals

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

# 3. Das finale Eingabefenster
class MemberInfoModal(discord.ui.Modal, title='Details eingeben'):
    def __init__(self, char_class, char_spec):
        super().__init__()
        self.char_class = char_class
        self.char_spec = char_spec

    char_name = discord.ui.TextInput(label='Charakter Name', placeholder='z.B. Bolontíku')
    real_name = discord.ui.TextInput(label='Vorname', placeholder='z.B. Rene')

    async def on_submit(self, interaction: discord.Interaction):
        date_str = datetime.now().strftime("%d.%m.%Y")
        thread_name = f"[{self.char_class}] {self.char_name.value} ({self.char_spec}) {self.real_name.value}"
        
        # Forum-Kanal finden
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        
        if isinstance(forum_channel, discord.ForumChannel):
            # Erstellt einen neuen Post im Forum
            await forum_channel.create_thread(
                name=thread_name,
                content=f"👤 **Mitglied:** {self.char_name.value} ({self.real_name.value})\n📅 **Beigetreten am:** {date_str}\n🛡️ **Klasse:** {self.char_class} - {self.char_spec}"
            )
            await interaction.response.send_message(f"✅ Post im Forum erstellt!", ephemeral=True)
        else:
            await interaction.response.send_message("Fehler: Forum-Kanal nicht gefunden!", ephemeral=True)

# 2. Das Dropdown für die Spec
class SpecSelectView(discord.ui.View):
    def __init__(self, char_class):
        super().__init__(timeout=None)
        options = [discord.SelectOption(label=s) for s in WOW_DATA[char_class]]
        self.add_item(self.SpecSelect(char_class, options))

    class SpecSelect(discord.ui.Select):
        def __init__(self, char_class, options):
            self.char_class = char_class
            super().__init__(placeholder="Spezialisierung wählen...", options=options)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_modal(MemberInfoModal(self.char_class, self.values[0]))

# 1. Die Hauptansicht mit dem Button
class GildenLeitungView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Button bleibt dauerhaft aktiv

    @discord.ui.button(label="Neues Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_member_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check ob Admin/Offizier
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            view = discord.ui.View()
            # Klassen-Dropdown hinzufügen
            options = [discord.SelectOption(label=cls) for cls in WOW_DATA.keys()]
            select = discord.ui.Select(placeholder="Klasse wählen...", options=options)
            
            async def class_callback(inter: discord.Interaction):
                await inter.response.send_message("Jetzt die Spec wählen:", view=SpecSelectView(select.values[0]), ephemeral=True)
            
            select.callback = class_callback
            view.add_item(select)
            await interaction.response.send_message("Wähle die Klasse des neuen Mitglieds:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Nur die Gildenleitung darf das!", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Button dauerhaft registrieren
        self.add_view(GildenLeitungView())

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """Erstellt die Nachricht mit dem Button"""
    await ctx.send("### 🏰 Gildenverwaltung\nKlicke auf den Button unten, um ein neues Mitglied in die Liste (Forum) aufzunehmen.", view=GildenLeitungView())

bot.run('MTQ5MzM3NzI2ODUxMTQwODIyOQ.GX5QN5.IXfQYxGqyYyWFeLYnFSUhoOQN5zNkvQrDmgD9c')