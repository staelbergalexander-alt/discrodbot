import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import re
import asyncio
import aiohttp
from datetime import datetime
from config import OFFIZIER_ROLLE_ID, FORUM_CHANNEL_ID, MITGLIED_ROLLE_ID, BEWERBER_ROLLE_ID, DB_FILE

class Recruitment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def setup(self, ctx):
        if any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
            view = GildenLeitungView(self)
            await ctx.send("### 🏰 Gildenverwaltung", view=view)

# --- MODAL FÜR ABLEHNUNGS-BEGRÜNDUNG ---

class DeclineReasonModal(discord.ui.Modal, title='Bewerbung ablehnen'):
    reason = discord.ui.TextInput(
        label='Begründung',
        style=discord.TextStyle.paragraph,
        placeholder='Z.B. Gear reicht noch nicht ganz aus...',
        required=True,
        max_length=500
    )

    def __init__(self, member_id):
        super().__init__()
        self.member_id = member_id

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="❌ Bewerbung abgelehnt",
            description=f"**Grund:** {self.reason.value}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)
        
        # Thread automatisch archivieren
        await asyncio.sleep(10)
        thread = interaction.channel
        if isinstance(thread, discord.Thread):
            await thread.edit(archived=True, locked=True)

# --- VIEWS ---

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen ✅", style=discord.ButtonStyle.success, custom_id="acc_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            if m_role: await member.add_roles(m_role)
            if b_role: await member.remove_roles(b_role)
            await interaction.response.send_message(f"✅ {member.mention} wurde aufgenommen! Post wird archiviert...")
            
            # Thread automatisch archivieren
            await asyncio.sleep(10)
            thread = interaction.channel
            if isinstance(thread, discord.Thread):
                await thread.edit(archived=True, locked=True)

    @discord.ui.button(label="Ablehnen ❌", style=discord.ButtonStyle.danger, custom_id="dec_btn")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeclineReasonModal(self.member_id))

class SuperQuickModal(discord.ui.Modal, title='Neuer Gilden-Eintrag'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder='Link einfügen...', required=True)
    real_name = discord.ui.TextInput(label='Vorname / Spielername', placeholder='z.B. Trav', required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⌛ Daten werden abgerufen...", ephemeral=True)
        
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
        if not match:
            return await interaction.followup.send("❌ Ungültiger Raider.io Link!", ephemeral=True)
        
        srv, name = match.group(1).capitalize(), match.group(2).capitalize()
        char_class = "Unbekannt"
        wcl_link = f"https://www.warcraftlogs.com/character/eu/{match.group(1)}/{match.group(2)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    char_class = data.get('class', 'Unbekannt')

        prompt = await interaction.channel.send(f"👉 Bitte erwähne jetzt den Discord-User (@Name) für **{name}**!")
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        
        try:
            msg = await self.cog.bot.wait_for('message', check=check, timeout=60)
            uid = msg.content.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
            member = interaction.guild.get_member(int(uid))
            
            if member:
                b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
                g_role = interaction.guild.get_role(GAST_ROLLE_ID)
                if b_role: await member.add_roles(b_role)
                if g_role: await member.remove_roles(g_role)
                
                with open(DB_FILE, "r") as f: db_data = json.load(f)
                db_data[str(member.id)] = {"chars": [{"name": name, "realm": srv}]}
                with open(DB_FILE, "w") as f: json.dump(db_data, f, indent=4)
                
                forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
                if forum:
                    embed = discord.Embed(title=f"🛡️ Neuer Eintrag: {name}", color=discord.Color.blue(), timestamp=datetime.now())
                    embed.add_field(name="Datum", value=datetime.now().strftime("%d.%m.%Y"), inline=True)
                    embed.add_field(name="Erstellt von", value=interaction.user.display_name, inline=True)
                    embed.add_field(name="Klasse", value=char_class, inline=True)
                    embed.add_field(name="Spieler", value=self.real_name.value, inline=True)
                    embed.add_field(name="Links", value=f"[Raider.io]({self.rio_link.value}) | [WarcraftLogs]({wcl_link})", inline=False)

                    thread_data = await forum.create_thread(name=f"{name} | {self.real_name.value}", embed=embed)
                    await thread_data.thread.send(content=f"💡 Entscheidung für {member.mention}:", view=ThreadActionView(member.id))
                
                await member.edit(nick=f"{name} | {self.real_name.value}")
            
            await prompt.delete()
            await msg.delete()
            
        except Exception as e:
            print(f"Fehler: {e}")

class GildenLeitungView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_mem_btn")
    async def add(self, interaction, button):
        await interaction.response.send_modal(SuperQuickModal(self.cog))

async def setup(bot):
    await bot.add_cog(Recruitment(bot))
