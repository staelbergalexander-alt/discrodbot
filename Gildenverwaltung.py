import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import os
import asyncio

# --- KONFIGURATION (Über Umgebungsvariablen oder Standardwerte) ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 'DEIN_TOKEN_LOKAL')
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 'DEIN_TOKEN_LOKAL')
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

    # Felder im Eingabefenster
    discord_search = discord.ui.TextInput(
        label='Discord User (Name oder ID)', 
        placeholder='ID per Rechtsklick kopieren für 100% Trefferquote'
    )
    ingame_name = discord.ui.TextInput(
        label='Ingame Charakter Name', 
        placeholder='z.B. Bolontíku'
    )
    real_name = discord.ui.TextInput(
        label='Vorname des Spielers', 
        placeholder='z.B. Rene'
    )
    server_name = discord.ui.TextInput(
        label='WoW-Server', 
        default=DEFAULT_SERVER_NAME
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 1. User auf Discord finden
        raw_input = self.discord_search.value.strip()
        user_id_str = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        
        member = None
        if user_id_str.isdigit():
            member = interaction.guild.get_member(int(user_id_str))
        if not member:
            member = discord.utils.get(interaction.guild.members, display_name=raw_input)
        if not member:
            member = discord.utils.get(interaction.guild.members, name=raw_input)

        # 2. Daten für Forum & Logs
        srv_slug = self.server_name.value.replace(" ", "-").lower()
        log_url = f"https://www.warcraftlogs.com/character/{REGION}/{srv_slug}/{self.ingame_name.value.lower()}"
        thread_name = f"[{self.char_class}] {self.ingame_name.value} ({self.char_spec}) {self.real_name.value}"
        
        # 3. Forum Post erstellen
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            await forum_channel.create_thread(
                name=thread_name,
                content=f"## Neuer Eintrag: {self.ingame_name.value}\n"
                        f"**Server:** {self.server_name.value}\n"
                        f"**Klasse:** {self.char_class} ({self.char_spec})\n"
                        f"**Spieler:** {self.real_name.value}\n\n"
                        f"📈 [Warcraft Logs Profil]({log_url})"
            )

        # 4. Nickname & Rollen Update
        status_update = ""
        if member:
            # Nickname ändern: "Charname (Vorname)"
            new_nick = f"{self.ingame_name.value} ({self.real_name.value})"
            try:
                await member.edit(nick=new_nick)
                status_update += f"✅ Nickname zu `{new_nick}` geändert.\n"
            except:
                status_update += "❌ Nickname-Rechte fehlen (Bot-Rolle zu niedrig?).\n"

            # Rolle geben
            role = discord.utils.get(interaction.guild.roles, name=self.char_class)
            if role:
                try:
                    await member.add_roles(role)
                    status_update += f"✅ Rolle `{self.char_class}` zugewiesen."
                except:
                    status_update += "❌ Rollen-Rechte fehlen."
        else:
            status_update = "⚠️ Discord-User wurde nicht gefunden. Bitte manuell anpassen."

        await interaction.response.send_message(f"✅ Forum-Eintrag erstellt!\n{status_update}", ephemeral=True)

class SpecSelect(discord.ui.Select):
    def __init__(self, char_class):
        self.char_class = char_class
        options = [discord.SelectOption(label=s) for s in WOW_DATA[char_class]]
        super().__init__(placeholder="Spezialisierung wählen...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MemberInfoModal(self.char_class, self.values[0]))
        # Auswahlmenü löschen für Kanalsauberkeit
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
                await inter.response.send_message(f"Gewählt: **{select.values[0]}**", view=spec_view)
            
            select.callback = class_callback
            view.add_item(select)
            await interaction.response.send_message("Wähle die Klasse des neuen Mitglieds:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True # Erlaubt das Finden von Usern und Ändern von Nicks
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(GildenLeitungView())

bot = GildenBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    # Räumt den Kanal auf
    await ctx.channel.purge(limit=5, check=lambda m: m.author == bot.user)
    await ctx.send("### 🏰 Gildenverwaltung\nKlicke auf den Button, um ein Mitglied im Forum zu registrieren, die Rolle zuzuweisen und den Namen anzupassen.", view=GildenLeitungView())
    await ctx.message.delete()

# Start
TOKEN = os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN_LOKAL'
bot.run(TOKEN)
