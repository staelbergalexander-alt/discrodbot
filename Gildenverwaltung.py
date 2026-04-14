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

def save_member(name, class_name, spec, rio):
    # Speichert das Mitglied in einer lokalen Datei
    data = {}
    if os.path.exists("members.json"):
        with open("members.json", "r") as f:
            data = json.load(f)
    
    data[name] = {"class": class_name, "spec": spec, "rio": rio}
    
    with open("members.json", "w") as f:
        json.dump(data, f)

async def update_member_list_message(guild):
    channel = guild.get_channel(MITGLIEDER_LISTE_KANAL_ID)
    if not channel: return

    if not os.path.exists("members.json"): return

    with open("members.json", "r") as f:
        members = json.load(f)

    # Sortieren nach Klassen
    sorted_members = {}
    for name, info in members.items():
        cls = info['class']
        if cls not in sorted_members: sorted_members[cls] = []
        sorted_members[cls].append(f"• **{name}** ({info['spec']}) - {info['rio']} RIO")

    embed = discord.Embed(title="🏰 Gildenmitglieder-Verzeichnis", color=discord.Color.gold(), timestamp=discord.utils.utcnow())
    
    for cls in sorted(sorted_members.keys()):
        content = "\n".join(sorted_members[cls])
        embed.add_field(name=f"🛡️ {cls.upper()}", value=content, inline=False)

    # Alte Nachricht suchen oder neue posten
    async for message in channel.history(limit=10):
        if message.author == guild.me and message.embeds:
            await message.edit(embed=embed)
            return
    
    await channel.send(embed=embed)

# --- VIEWS (Annehmen Button angepasst) ---

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id, char_data):
        super().__init__(timeout=None)
        self.member_id = member_id
        self.char_data = char_data # Hier speichern wir Name, Klasse, Spec, Rio

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role, b_role = interaction.guild.get_role(MITGLIED_ROLLE_ID), interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
                
                # --- LISTE AKTUALISIEREN ---
                save_member(self.char_data['name'], self.char_data['class'], self.char_data['spec'], self.char_data['rio'])
                await update_member_list_message(interaction.guild)
                
                await interaction.response.send_message(f"✅ {member.mention} aufgenommen & Liste aktualisiert!")
                await asyncio.sleep(5); await interaction.channel.delete()
            except: await interaction.response.send_message("Rechte fehlen!", ephemeral=True)

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        from __main__ import RejectModal # Import fix
        await interaction.response.send_modal(RejectModal(self.member_id))

# --- MODAL (Datenweitergabe an View) ---

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', required=True)
    discord_search = discord.ui.TextInput(label='Discord User', required=True)
    real_name = discord.ui.TextInput(label='Vorname', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
        if not match: return await interaction.followup.send("❌ Link-Fehler!", ephemeral=True)
        
        srv, name = match.group(1), match.group(2)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=mythic_plus_scores_by_season:current") as resp:
                if resp.status != 200: return await interaction.followup.send("❌ API Fehler!", ephemeral=True)
                data = await resp.json()

        char_data = {
            "name": data['name'],
            "class": data['class'],
            "spec": data['active_spec_name'] or "DD",
            "rio": data['mythic_plus_scores_by_season'][0]['scores']['all'] if 'mythic_plus_scores_by_season' in data else 0
        }

        # User finden & Thread erstellen (wie vorher)
        raw_input = self.discord_search.value.strip()
        user_id = raw_input.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
        member = interaction.guild.get_member(int(user_id)) if user_id.isdigit() else discord.utils.get(interaction.guild.members, display_name=raw_input)

        forum_channel = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            res = await forum_channel.create_thread(
                name=f"[{char_data['class']}] {char_data['name']} | {self.real_name.value}",
                content=f"### 🛡️ Bewerbung: {char_data['name']}\n**Klasse:** {char_data['class']} | **Spec:** {char_data['spec']}\n**Score:** {char_data['rio']}"
            )
            
            # WICHTIG: Wir geben char_data an die View weiter!
            view = ThreadActionView(member.id, char_data) if member else None
            if view: await res.thread.send("💡 Entscheidung:", view=view)
            
            # Rollen-Update (Gast -> Bewerber)
            if member:
                try:
                    await member.edit(nick=f"{char_data['name']} | {self.real_name.value}")
                    c_role = discord.utils.get(interaction.guild.roles, name=char_data['class'])
                    b_role, g_role = interaction.guild.get_role(BEWERBER_ROLLE_ID), interaction.guild.get_role(GAST_ROLLE_ID)
                    if g_role: await member.remove_roles(g_role)
                    if c_role: await member.add_roles(c_role)
                    if b_role: await member.add_roles(b_role)
                except: pass

        await interaction.followup.send("✅ Thread & Bewerber-Status erstellt!", ephemeral=True)

# --- REJECT MODAL (Muss definiert sein) ---
class RejectModal(discord.ui.Modal, title='Ablehnung'):
    reason = discord.ui.TextInput(label='Grund', style=discord.TextStyle.paragraph)
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
        await interaction.response.send_message(f"❌ Abgelehnt: {self.reason.value}")
        await interaction.channel.edit(locked=True, archived=True)

# --- BOT REST (Setup / Run) ---
class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            await interaction.response.send_modal(SuperQuickModal())
        else: await interaction.response.send_message("Keine Rechte!", ephemeral=True)

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default(); intents.message_content = True; intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self): self.add_view(GildenLeitungView())

bot = GildenBot()
@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())

bot.run(os.getenv('DISCORD_TOKEN') or 'DEIN_TOKEN')
