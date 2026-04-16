import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import re
import aiohttp
from discord.ext import tasks
from datetime import datetime, timedelta

# --- KONFIGURATION (Railway Variablen) ---
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
RAID_READY_ROLLE_ID = int(os.getenv('RAID_READY_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID') or 0) # Wo die Logs gepostet werden
ARCHIV_CHANNEL_ID = int(os.getenv('ARCHIV_CHANNEL_ID') or 0) # Das Archiv
PLANUNGS_CHANNEL_ID = int(os.getenv('PLANUNGS_CHANNEL_ID') or 0)
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
DB_FILE = "mitglieder_db.json"
REGION = "eu"

# --- KONFIGURATION ---
DB_FOLDER = "/app/data" # Der Pfad zum Volume
DB_FILE = os.path.join(DB_FOLDER, "mitglieder_db.json")

# Erstelle den Ordner, falls er im Volume noch nicht existiert
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)

# Der Rest der Datenbank-Funktionen bleibt gleich:
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: 
            try: return json.load(f)
            except: return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f: 
        json.dump(data, f, indent=4)
        
def get_raid_week_dates():
    now = datetime.now()
    days_until_thursday = (3 - now.weekday() + 7) % 7
    if days_until_thursday == 0: days_until_thursday = 7
    next_thursday = now + timedelta(days=days_until_thursday)
    following_wednesday = next_thursday + timedelta(days=6)
    return next_thursday.strftime("%d.%m."), following_wednesday.strftime("%d.%m.")

# --- GEAR CHECK LOGIK ---
async def fetch_gear_data(session, realm, name):
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
    async with session.get(url) as resp:
        if resp.status != 200: return None
        data = await resp.json()
        items = data.get('gear', {}).get('items', {})
        ilvl = data.get('gear', {}).get('item_level_equipped', 0)
        
        missing_enchant = False
        empty_sockets = 0
        enchantable_slots = ['neck', 'back', 'chest', 'bracers', 'cloak', 'legs', 'boots', 'mainhand', 'offhand', 'finger1', 'finger2']
        
        for slot, info in items.items():
            if slot in enchantable_slots and info.get('enchant') is None:
                missing_enchant = True
            empty_sockets += info.get('gems_missing', 0)
            
        return {
            "ilvl": ilvl,
            "missing_enchant": missing_enchant,
            "empty_sockets": empty_sockets
        }

# --- VIEWS ---
class RaidPollView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction: discord.Interaction, day_index: int):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_index]
        user_mention = interaction.user.mention
        current_voters = field.value.split(", ") if field.value != "Keine Stimmen" else []
        
        if user_mention in current_voters: current_voters.remove(user_mention)
        else: current_voters.append(user_mention)
        
        new_value = ", ".join(current_voters) if current_voters else "Keine Stimmen"
        embed.set_field_at(day_index, name=f"{self.days_order[day_index]} ({len(current_voters)})", value=new_value, inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="poll_0")
    async def v_0(self, i, b): await self.handle_vote(i, 0)
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="poll_1")
    async def v_1(self, i, b): await self.handle_vote(i, 1)
    @discord.ui.button(label="Sa", style=discord.ButtonStyle.gray, custom_id="poll_2")
    async def v_2(self, i, b): await self.handle_vote(i, 2)
    @discord.ui.button(label="So", style=discord.ButtonStyle.gray, custom_id="poll_3")
    async def v_3(self, i, b): await self.handle_vote(i, 3)
    @discord.ui.button(label="Mo", style=discord.ButtonStyle.gray, custom_id="poll_4")
    async def v_4(self, i, b): await self.handle_vote(i, 4)
    @discord.ui.button(label="Di", style=discord.ButtonStyle.gray, custom_id="poll_5")
    async def v_5(self, i, b): await self.handle_vote(i, 5)
    @discord.ui.button(label="Mi", style=discord.ButtonStyle.gray, custom_id="poll_6")
    async def v_6(self, i, b): await self.handle_vote(i, 6)

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
        await asyncio.sleep(3)
        await interaction.channel.edit(locked=True, archived=True)

class ThreadActionView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        if member:
            try:
                # Rollen-Objekte holen
                m_role = interaction.guild.get_role(MITGLIED_ROLLE_ID)
                b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
                g_role = interaction.guild.get_role(GAST_ROLLE_ID) # Gast Rolle
                
                roles_to_add = []
                roles_to_remove = []

                if m_role: roles_to_add.append(m_role)
                if b_role: roles_to_remove.append(b_role)
                if g_role: roles_to_remove.append(g_role) # Gast zum Entfernen markieren

                # Rollen-Update ausführen
                if roles_to_add: await member.add_roles(*roles_to_add)
                if roles_to_remove: await member.remove_roles(*roles_to_remove)
                
                await interaction.response.send_message(f"✅ {member.mention} als Mitglied aufgenommen und Gast/Bewerber-Rollen entfernt!")
                
                # Kurze Pause bevor der Thread gelöscht wird
                await asyncio.sleep(5)
                await interaction.channel.delete()
                
            except Exception as e: 
                await interaction.response.send_message(f"Fehler bei Rollenvergabe: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("User nicht mehr auf dem Server gefunden.", ephemeral=True)
                
    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Hier bleibt deine Ablehnungs-Logik (Modal oder Nachricht)
        await interaction.response.send_message("❌ Bewerbung wurde abgelehnt.")
        
class SuperQuickModal(discord.ui.Modal, title='Schnell-Registrierung'):
    rio_link = discord.ui.TextInput(label='Raider.io Link', placeholder="https://raider.io/characters/eu/...", required=True)
    real_name = discord.ui.TextInput(label='Vorname des Spielers', placeholder="z.B. Max", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Den Namen des Offiziers speichern, der das Modal abgeschickt hat
        ersteller = interaction.user.display_name 
        
        await interaction.response.send_message("✅ Daten empfangen! Erwähne (@Name) jetzt den User im Chat.", ephemeral=True)
        
        def check(m): 
            return m.author == interaction.user and m.channel == interaction.channel
            
        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=60.0)
            raw_id = msg.content.replace("<@", "").replace("!", "").replace(">", "").replace("&", "")
            target_member = interaction.guild.get_member(int(raw_id)) if raw_id.isdigit() else None
            
            if not target_member: 
                return await interaction.followup.send("❌ User nicht gefunden.", ephemeral=True)
            
            # --- ROLLEN-MANAGEMENT ---
            b_role = interaction.guild.get_role(BEWERBER_ROLLE_ID)
            g_role = interaction.guild.get_role(GAST_ROLLE_ID)
            
            try:
                if g_role: await target_member.remove_roles(g_role)
                if b_role: await target_member.add_roles(b_role)
            except:
                print("Rollenfehler beim Anlegen: Rechte prüfen!")

            # Link parsen
            match = re.search(r'characters/eu/([^/]+)/([^/]+)', self.rio_link.value.lower())
            if not match: 
                return await interaction.followup.send("❌ Raider.io Link ungültig!", ephemeral=True)
            
            srv_raw, name_raw = match.group(1), match.group(2)
            srv, char_name = srv_raw.capitalize(), name_raw.capitalize()
            heute = datetime.now().strftime("%d.%m.%Y")
            wcl_url = f"https://www.warcraftlogs.com/character/eu/{srv_raw.lower()}/{name_raw.lower()}"

            # Datenbank Update
            db = load_db()
            db[str(target_member.id)] = {"name": char_name, "realm": srv}
            save_db(db)

            # API & Forum-Thread
            api_url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={char_name}&fields=gear"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    char_class = "Unbekannt"
                    if resp.status == 200:
                        data = await resp.json()
                        char_class = data.get('class', "Unbekannt")

                    forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
                    if forum:
                        content_text = (
                            f"### 🛡️ Neuer Eintrag: {char_name}\n"
                            f"**Datum:** {heute}\n"
                            f"**Erstellt von:** {ersteller}\n" # <--- NEU
                            f"**Klasse:** {char_class}\n"
                            f"**Spieler:** {self.real_name.value}\n"
                            f"**Links:** [Raider.io]({self.rio_link.value}) | [WarcraftLogs]({wcl_url})"
                        )
                        
                        res = await forum.create_thread(
                            name=f"[{char_class}] {char_name} | {self.real_name.value}",
                            content=content_text
                        )
                        await res.thread.send(f"💡 Entscheidung für {target_member.mention}:", view=ThreadActionView(target_member.id))
                        await target_member.edit(nick=f"{char_name} | {self.real_name.value}")
            
            await msg.delete()
            
        except Exception as e: 
            await interaction.followup.send(f"Fehler: {e}", ephemeral=True)
            
class GildenLeitungView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Mitglied eintragen", style=discord.ButtonStyle.green, custom_id="add_btn")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
            await interaction.response.send_modal(SuperQuickModal())
        else: await interaction.response.send_message("Keine Rechte!", ephemeral=True)

# --- BOT KLASSE ---
class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.archive_task.start()
    
    async def setup_hook(self):
        self.add_view(GildenLeitungView())
        self.add_view(RaidPollView())
        if SERVER_ID != 0:
            MY_GUILD = discord.Object(id=SERVER_ID)
            self.tree.copy_global_to(guild=MY_GUILD)
            await self.tree.sync(guild=MY_GUILD)

    @tasks.loop(hours=6) # Prüft alle 6 Stunden
    async def archive_logs(self):
        guild = self.get_guild(SERVER_ID)
        if not guild: return
        
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        archiv_channel = guild.get_channel(ARCHIV_CHANNEL_ID)
        if not log_channel or not archiv_channel: return

        cutoff = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(hours=12)
        log_pattern = re.compile(r"https:\/\/(www\.)?warcraftlogs\.com\/reports\/[a-zA-Z0-9]+")

        async for message in log_channel.history(limit=50):
            # Wenn Nachricht älter als 12h ist UND einen Log-Link enthält
            if message.created_at < cutoff and log_pattern.search(message.content):
                ts = message.created_at.strftime("%d.%m.%Y")
                content = f"**Raid-Log vom {ts}** (Archiv):\n{message.content}"
                await archiv_channel.send(content)
                await message.delete()
                await asyncio.sleep(1)

bot = GildenBot()

@bot.tree.command(name="archive_logs", description="Verschiebt Logs manuell ins Archiv")
async def archive_logs(interaction: discord.Interaction):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("Keine Rechte!", ephemeral=True)
    
    await interaction.response.send_message("Suche nach Logs zum Verschieben...", ephemeral=True)
    log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
    archiv_channel = interaction.guild.get_channel(ARCHIV_CHANNEL_ID)
    
    moved = 0
    log_pattern = re.compile(r"https:\/\/(www\.)?warcraftlogs\.com\/reports\/[a-zA-Z0-9]+")
    
    async for msg in log_channel.history(limit=100):
        if log_pattern.search(msg.content):
            await archiv_channel.send(f"**Manueller Archiv-Eintrag ({msg.created_at.strftime('%d.%m.')}):**\n{msg.content}")
            await msg.delete()
            moved += 1
    await interaction.followup.send(f"✅ {moved} Logs verschoben.")

# --- BEFEHLE ---
@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync(guild=discord.Object(id=SERVER_ID))
    await ctx.send("✅ Slash-Commands synchronisiert!")

@bot.command()
async def setup(ctx):
    if any(role.id == OFFIZIER_ROLLE_ID for role in ctx.author.roles):
        await ctx.send("### 🏰 Gildenverwaltung", view=GildenLeitungView())

@bot.command()
async def raidumfrage(ctx):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in ctx.author.roles): return
    start, end = get_raid_week_dates()
    embed = discord.Embed(title=f"⚔️ Raid-Umfrage ({start} - {end})", color=discord.Color.blue())
    for d in ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]:
        embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
    await ctx.send(embed=embed, view=RaidPollView())

@bot.tree.command(name="add_member_rio", description="Füge ein Mitglied per Raider.io Link hinzu")
async def add_member_rio(interaction: discord.Interaction, user: discord.Member, rio_link: str):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("❌ Keine Rechte!", ephemeral=True)
    match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
    if not match: return await interaction.response.send_message("❌ Ungültiger Link!", ephemeral=True)
    
    server, charname = match.group(1).capitalize(), match.group(2).capitalize()
    db = load_db()
    db[str(user.id)] = {"name": charname, "realm": server}
    save_db(db)
    await interaction.response.send_message(f"✅ Verknüpft: {user.mention} ↔️ **{charname}** ({server})")

@bot.tree.command(name="list_members", description="Zeigt alle registrierten Mitglieder")
async def list_members(interaction: discord.Interaction):
    db = load_db()
    if not db: return await interaction.response.send_message("Die Liste ist leer.", ephemeral=True)
    liste = [f"• <@{uid}>: **{info['name']}** ({info['realm']})" for uid, info in db.items()]
    await interaction.response.send_message(embed=discord.Embed(title="Mitglieder", description="\n".join(liste), color=discord.Color.gold()))
    
@bot.tree.command(name="remove_member", description="Löscht ein Mitglied aus der Raid-Datenbank")
@app_commands.describe(user="Der Discord-User, der entfernt werden soll")
async def remove_member(interaction: discord.Interaction, user: discord.Member):
    # Prüfung auf Offizier-Rechte
    if not any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("❌ Keine Rechte!", ephemeral=True)

    db = load_db()
    user_id_str = str(user.id)

    if user_id_str in db:
        char_info = db.pop(user_id_str)
        save_db(db)
        await interaction.response.send_message(
            f"✅ **{char_info['name']}** (<@{user.id}>) wurde aus der Datenbank gelöscht.", 
            ephemeral=False
        )
    else:
        await interaction.response.send_message(
            f"❌ Dieser User ist gar nicht in der Datenbank registriert.", 
            ephemeral=True
        )
        
@bot.tree.command(name="check_raid_ready", description="Prüft Gear und vergibt automatisch die Raid-Ready Rolle")
async def check_raid_ready(interaction: discord.Interaction, min_ilvl: int = 270):
    await interaction.response.defer()
    
    db = load_db()
    ready_list, not_ready_list = [], []
    rr_role = interaction.guild.get_role(RAID_READY_ROLLE_ID)
    
    if not rr_role:
        return await interaction.followup.send("⚠️ Fehler: Raid-Ready Rolle wurde nicht gefunden. Prüfe die ID!")

    async with aiohttp.ClientSession() as session:
        for uid, info in db.items():
            member = interaction.guild.get_member(int(uid))
            if not member: continue

            res = await fetch_gear_data(session, info['realm'], info['name'])
            if res:
                warns = []
                if res['empty_sockets'] > 0: warns.append(f"💎 {res['empty_sockets']} Gems")
                
                is_ready = (res['ilvl'] >= min_ilvl and not warns)
                txt = f"<@{uid}>: **{res['ilvl']}**" + (f" ({', '.join(warns)} fehlt!)" if warns else "")

                try:
                    if is_ready:
                        ready_list.append(f"✅ {txt}")
                        if rr_role not in member.roles:
                            await member.add_roles(rr_role)
                    else:
                        not_ready_list.append(f"❌ {txt}")
                        if rr_role in member.roles:
                            await member.remove_roles(rr_role)
                except Exception as e:
                    print(f"Rollen-Fehler bei {member.display_name}: {e}")

            await asyncio.sleep(0.1) # Kurze Pause gegen API-Limits

    embed = discord.Embed(
        title="🛡️ Raid-Ready Status & Rollen-Update", 
        description=f"Geprüftes Itemlevel: **{min_ilvl}+**",
        color=discord.Color.blue()
    )
    embed.add_field(name="✅ Ready (Rolle vergeben)", value="\n".join(ready_list) or "Niemand", inline=False)
    embed.add_field(name="❌ Nachbessern (Rolle entzogen)", value="\n".join(not_ready_list) or "Niemand", inline=False)
    
    await interaction.followup.send(embed=embed)
bot.run(os.getenv('DISCORD_TOKEN'))
