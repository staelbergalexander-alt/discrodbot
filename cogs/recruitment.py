import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import re
import asyncio
from config import OFFIZIER_ROLLE_ID, FORUM_CHANNEL_ID, MITGLIED_ROLLE_ID, BEWERBER_ROLLE_ID, GAST_ROLLE_ID

class Recruitment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "/app/data/mitglieder_db.json"

    # Hilfsfunktion zum Speichern der DB
    def save_db(self, data):
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=4)

    @commands.command()
    async def setup(self, ctx):
        """Erstellt das Panel für die Gildenleitung"""
        if any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
            view = GildenLeitungView(self)
            await ctx.send("### 🏰 Gildenverwaltung", view=view)

# --- VIEWS & MODALS FÜR RECRUITMENT ---

class ThreadActionView(discord.ui.View):
    def __init__(self, cog, member_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="acc_btn")
    async def accept(self, interaction, button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            if m_role: await member.add_roles(m_role)
            if b_role: await member.remove_roles(b_role)
            await interaction.response.send_message(f"✅ {member.mention} aufgenommen!")
            await asyncio.sleep(5)
            await interaction.channel.delete()

class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', required=True)
    real_name = discord.ui.TextInput(label='Vorname', required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction):
        await interaction.response.send_message("✅ Erwähne (@Name) jetzt den User!", ephemeral=True)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        
        try:
            msg = await self.cog.bot.wait_for('message', check=check, timeout=60)
            uid = msg.content.replace("<@", "").replace("!", "").replace(">", "")
            member = interaction.guild.get_member(int(uid))
            
            if member:
                match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
                if match:
                    srv, name = match.group(1).capitalize(), match.group(2).capitalize()
                    
                    # DB Update
                    with open(self.cog.db_path, "r") as f: data = json.load(f)
                    data[str(member.id)] = {"chars": [{"name": name, "realm": srv}]}
                    self.cog.save_db(data)
                    
                    # Forum & Nickname
                    forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
                    if forum:
                        thread = await forum.create_thread(name=f"{name} | {self.real_name.value}", content=f"Bewerbung: {self.rio_link.value}")
                        await thread.thread.send(f"Entscheidung für {member.mention}:", view=ThreadActionView(self.cog, member.id))
                    await member.edit(nick=f"{name} | {self.real_name.value}")
            await msg.delete()
        except: pass

class GildenLeitungView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_mem")
    async def add(self, interaction, button):
        await interaction.response.send_modal(SuperQuickModal(self.cog))

async def setup(bot):
    await bot.add_cog(Recruitment(bot))
