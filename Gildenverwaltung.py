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
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID'))
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

class MemberInfoModal(discord.ui.Modal, title='Mitglied Details'):
    def __init__(self, char_class, char_spec):
        super().__init__()
        self.char_class = char_class
        self.char_spec = char_spec

    rio_link = discord.ui.TextInput(label='Raider.io Link (Optional)', placeholder='Einfügen für Auto-Fill von Name/Server', required=False)
    discord_search = discord.ui.TextInput(label='Discord User Suche', placeholder='Discord ID')
    ingame_name = discord.ui.TextInput(label='Char Name (falls kein Link)', required=False)
    real_name = discord.ui.TextInput(label='Vorname')
    server_name = discord.ui.TextInput(label='Server', default=DEFAULT_SERVER_NAME, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        # --- AUTO-FILL LOGIK ---
        final_char = self.ingame_name.value
        final_server = self.server_name.value
        
        if self.rio_link.value:
            # Extrahiert Name und Server aus: https://raider.io/characters/eu/blackhand/bolontiku
            match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
            if match:
                final_server = match.group(1).capitalize().replace("-", " ")
                final_char = match.group(2).capitalize()

        if not final_char:
            return await interaction.response.send_message("Fehler: Kein Name gefunden (Link oder Textfeld nutzen).", ephemeral=True)

        # 1. User finden
        raw_input = self.discord_search.value.strip()
        user_id = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = interaction.guild.get_member(int(user_id)) if user_id.isdigit() else discord.utils.get(interaction.guild.members, display_name=raw_input)

        # 2. Links & Thread
        srv_slug = final_server.replace(" ", "-").lower()
        wcl_url = f"https://www.warcraftlogs.com/character/{REGION}/{srv_slug}/{final_char.lower()}"
        rio_url = f"https://raider.io/characters/{REGION}/{srv_slug}/{final_char.lower()}"
        
        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            res = await forum_channel.create_thread(
                name=f"[{self.char_class}] {final_char} | {self.real_name.value}",
                content=f"### 🛡️ Neuer Eintrag: {final_char}\n**Klasse:** {self.char_class} ({self.char_spec})\n"
                        f"**Spieler:** {self.real_name.value} | **Server:** {final_server}\n\n"
                        f"📈 **Profile:**\n• [Warcraft Logs]({wcl_url})\n• [Raider.io]({rio_url})"
            )
            
            if member:
                await res.thread.send("💡 **Entscheidung treffen:**", view=ThreadActionView(member.id))
                try:
                    await member.edit(nick=f"{final_char} | {self.real_name.value}")
                    c_role, b_role, g_role = discord.utils.get(interaction.guild.roles, name=self.char_class), interaction.guild.get_role(BEWERBER_ROLLE_ID), interaction.guild.get_role(GAST_ROLLE_ID)
                    if g_role: await member.remove_roles(g_role)
                    if c_role: await member.add_roles(c_role)
                    if b_role: await member.add_roles(b_role)
                except: pass
            await interaction.response.send_message("Eintrag erstellt!", ephemeral=True)

class SpecSelect(discord.ui.Select):
    def __init__(self, char_class):
        self.char_class = char_class
        super().__init__(placeholder="Spezialisierung wählen...", options=[discord.SelectOption(label=s) for s in WOW_DATA[char_class]])
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

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default(); intents.message_content = True; intents.members = True
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
