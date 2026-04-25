import discord
from discord.ext import commands
import os
import json
import re
import asyncio
import aiohttp
import urllib.parse
from datetime import datetime

# Importiere deine IDs aus der config.py
from config import (
    OFFIZIER_ROLLE_ID, 
    FORUM_CHANNEL_ID, 
    MITGLIED_ROLLE_ID, 
    BEWERBER_ROLLE_ID, 
    DB_FILE, 
    GAST_ROLLE_ID
)

# --- MODAL FÜR ABLEHNUNGS-BEGRÜNDUNG ---

class DeclineReasonModal(discord.ui.Modal, title='Bewerbung ablehnen'):
    reason = discord.ui.TextInput(label='Begründung', style=discord.TextStyle.paragraph, required=True)

    def __init__(self, member_id):
        super().__init__()
        self.member_id = member_id

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.member_id)
        
        if member:
            g_role = interaction.guild.get_role(GAST_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if g_role: await member.add_roles(g_role)
                if b_role: await member.remove_roles(b_role)
            except:
                pass

        embed = discord.Embed(
            title="❌ Bewerbung abgelehnt",
            description=f"**Mitglied:** {member.mention if member else 'Unbekannt'}\n**Grund:** {self.reason.value}",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        await interaction.response.send_message(embed=embed)
        
        if isinstance(interaction.channel, discord.Thread):
            await asyncio.sleep(5)
            await interaction.channel.edit(name=f"❌ ABGELEHNT - {interaction.channel.name}", archived=True, locked=True)

# --- VIEWS FÜR DIE BUTTONS ---

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id=None):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen ✅", style=discord.ButtonStyle.success, custom_id="acc_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_id = self.member_id
        if target_id is None and interaction.message.mentions:
            target_id = interaction.message.mentions[0].id

        if not target_id:
            return await interaction.response.send_message("❌ Fehler: Mitglieds-ID nicht gefunden.", ephemeral=True)

        member = interaction.guild.get_member(target_id)
        if member:
            m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if m_role: await member.add_roles(m_role)
                if b_role: await member.remove_roles(b_role)
            except:
                pass
            
            await interaction.response.send_message(f"✅ {member.mention} wurde aufgenommen! Dieser Thread wird in 5 Sekunden gelöscht...")
            
            await asyncio.sleep(5)
            if isinstance(interaction.channel, discord.Thread):
                await interaction.channel.delete()

    @discord.ui.button(label="Ablehnen ❌", style=discord.ButtonStyle.danger, custom_id="dec_btn")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_id = self.member_id
        if target_id is None and interaction.message.mentions:
            target_id = interaction.message.mentions[0].id
            
        if not target_id:
            return await interaction.response.send_message("❌ Fehler: ID nicht gefunden.", ephemeral=True)
            
        await interaction.response.send_modal(DeclineReasonModal(target_id))

class GildenLeitungView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_mem_btn")
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SuperQuickModal(self.cog))

# --- MODAL FÜR DEN EINTRAG ---

class SuperQuickModal(discord.ui.Modal, title='Neuer Gilden-Eintrag'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder='Link einfügen...', required=True)
    real_name = discord.ui.TextInput(label='Vorname / Spielername', placeholder='z.B. Alex', required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⌛ Daten werden abgerufen...", ephemeral=True)
        
        # Aktuelles Datum für den Eintritt
        join_date = datetime.now().strftime("%d.%m.%Y")
        
        # 1. Sonderzeichen-Handling (URL Decoding)
        decoded_url = urllib.parse.unquote(self.rio_link.value)
        match = re.search(r'characters/eu/([^/]+)/([^/]+)', decoded_url.lower())
        
        if not match:
            return await interaction.followup.send("❌ Ungültiger Raider.io Link!", ephemeral=True)
        
        srv_raw, name_raw = match.group(1), match.group(2)
        safe_srv = urllib.parse.quote(srv_raw)
        safe_name = urllib.parse.quote(name_raw)
        
        char_class = "Unbekannt"
        wcl_link = f"https://www.warcraftlogs.com/character/eu/{safe_srv}/{safe_name}"
        
        async with aiohttp.ClientSession() as session:
            api_url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={safe_srv}&name={safe_name}"
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    char_class = data.get('class', 'Unbekannt')
                    final_name = data.get('name', name_raw.capitalize())
                    final_srv = data.get('realm', srv_raw.capitalize())
                else:
                    final_name = name_raw.capitalize()
                    final_srv = srv_raw.capitalize()

        prompt = await interaction.channel.send(f"👉 Bitte erwähne jetzt den Discord-User (@Name) für **{final_name}**!")
        
        def check(m): 
            return m.author == interaction.user and m.channel == interaction.channel
        
        try:
            msg = await self.cog.bot.wait_for('message', check=check, timeout=60)
            uid_match = re.search(r'(\d+)', msg.content)
            
            if not uid_match:
                return await interaction.followup.send("❌ Keine gültige Discord-ID gefunden!", ephemeral=True)
            
            uid = uid_match.group(1)
            member = interaction.guild.get_member(int(uid))
            
            if member:
                # Rollen & Nickname
                b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
                g_role = interaction.guild.get_role(GAST_ROLLE_ID)
                try:
                    if b_role: await member.add_roles(b_role)
                    if g_role: await member.remove_roles(g_role)
                    new_nick = f"{final_name} | {self.real_name.value}"[:32]
                    await member.edit(nick=new_nick)
                except:
                    pass
                
                # 3. Datenbank Speicherung (Inkl. Eintrittsdatum)
                if not os.path.exists(DB_FILE):
                    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
                    with open(DB_FILE, "w", encoding="utf-8") as f:
                        json.dump({}, f)
                
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    try: db_data = json.load(f)
                    except: db_data = {}
                
                # Datenstruktur erweitern
                db_data[str(member.id)] = {
                    "chars": [{"name": final_name, "realm": final_srv}],
                    "join_date": join_date,
                    "real_name": self.real_name.value
                }
                
                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(db_data, f, indent=4, ensure_ascii=False)
                
                # Forum Thread erstellen
                forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
                if forum:
                    thread_title = f"[{char_class}] {final_name} | {self.real_name.value}"[:100]
                    
                    embed = discord.Embed(
                        title=f"🛡️ Neuer Eintrag: {final_name}", 
                        color=discord.Color.blue(), 
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Klasse", value=char_class, inline=True)
                    embed.add_field(name="Spieler", value=self.real_name.value, inline=True)
                    embed.add_field(name="Server", value=final_srv, inline=False)
                    embed.add_field(name="Eintrittsdatum", value=join_date, inline=True)
                    embed.add_field(
                        name="Links", 
                        value=f"[Raider.io]({self.rio_link.value}) | [WarcraftLogs]({wcl_link})", 
                        inline=False
                    )

                    thread_data = await forum.create_thread(name=thread_title, embed=embed)
                    await thread_data.thread.send(
                        content=f"💡 Entscheidung für {member.mention}:", 
                        view=ThreadActionView(member.id)
                    )
            
            await prompt.delete()
            await msg.delete()
            
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Zeit abgelaufen.", ephemeral=True)
        except Exception as e:
            print(f"Fehler: {e}")
            await interaction.followup.send(f"❌ Fehler: {e}", ephemeral=True)

# --- COG KLASSE ---

class Recruitment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup")
    async def setup_cmd(self, ctx):
        if any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
            await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView(self))
        else:
            await ctx.send("❌ Keine Berechtigung.", delete_after=10)

async def setup(bot):
    cog = Recruitment(bot)
    await bot.add_cog(cog)
    bot.add_view(ThreadActionView())
    bot.add_view(GildenLeitungView(cog))