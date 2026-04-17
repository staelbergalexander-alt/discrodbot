import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import re
import asyncio
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

# --- VIEWS & MODALS ---

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="acc_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            if m_role: await member.add_roles(m_role)
            if b_role: await member.remove_roles(b_role)
            await interaction.response.send_message(f"✅ {member.mention} wurde aufgenommen!")
            # Optional: Thread nach Aufnahme schließen oder sperren

class SuperQuickModal(discord.ui.Modal, title='Neuer Gilden-Eintrag'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder='Link einfügen...', required=True)
    wcl_link = discord.ui.TextInput(label='WarcraftLogs Link (Optional)', required=False)
    real_name = discord.ui.TextInput(label='Vorname / Spielername', placeholder='z.B. Trav', required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⌛ Verarbeite Daten...", ephemeral=True)
        
        # User-Erwähnung abfragen (wie im alten Code)
        def check(m): return m.author == interaction.user and m.channel == interaction.channel
        prompt = await interaction.channel.send("👉 Bitte erwähne jetzt den Discord-User (@Name)!")
        
        try:
            msg = await self.cog.bot.wait_for('message', check=check, timeout=60)
            uid = msg.content.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
            member = interaction.guild.get_member(int(uid))
            
            if member:
                match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
                if match:
                    srv, name = match.group(1).capitalize(), match.group(2).capitalize()
                    
                    # Datenbank-Eintrag
                    with open(DB_FILE, "r") as f: data = json.load(f)
                    data[str(member.id)] = {"chars": [{"name": name, "realm": srv}]}
                    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)
                    
                    # --- FORUM EMBED ERSTELLEN (Layout wie im Bild) ---
                    forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
                    if forum:
                        embed = discord.Embed(
                            title=f"🛡️ Neuer Eintrag: {name}",
                            color=discord.Color.blue(),
                            timestamp=datetime.now()
                        )
                        embed.add_field(name="Datum", value=datetime.now().strftime("%d.%m.%Y"), inline=True)
                        embed.add_field(name="Erstellt von", value=interaction.user.display_name, inline=True)
                        embed.add_field(name="Klasse", value="Wird geladen...", inline=True) # Manuell oder via API
                        embed.add_field(name="Spieler", value=self.real_name.value, inline=True)
                        
                        links = f"[Raider.io]({self.rio_link.value})"
                        if self.wcl_link.value:
                            links += f" | [WarcraftLogs]({self.wcl_link.value})"
                        embed.add_field(name="Links", value=links, inline=False)

                        # Thread erstellen
                        thread_data = await forum.create_thread(name=f"{name} | {self.real_name.value}", embed=embed)
                        
                        # Entscheidungs-Nachricht mit Buttons
                        await thread_data.thread.send(
                            content=f"💡 Entscheidung für {member.mention} | {self.real_name.value}:",
                            view=ThreadActionView(member.id)
                        )
                    
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
