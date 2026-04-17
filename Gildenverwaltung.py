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

# Hilfs-Dict für WoW Klassen-Farben (Hex)
CLASS_COLORS = {
    "Death Knight": 0xC41E3A, "Demon Hunter": 0xA330C9, "Druid": 0xFF7C0A,
    "Evoker": 0x33937F, "Hunter": 0xAAD372, "Mage": 0x3FC7EB,
    "Monk": 0x00FF98, "Paladin": 0xF48CBA, "Priest": 0xFFFFFF,
    "Rogue": 0xFFF468, "Shaman": 0x0070DD, "Warlock": 0x8788EE, "Warrior": 0xC69B6D
}


# --- KONFIGURATION ---
DB_FOLDER = "/app/data" # Der Pfad zum Volume
DB_FILE = os.path.join(DB_FOLDER, "mitglieder_db.json")
DASHBOARD_FILE = os.path.join(DB_FOLDER, "dashboard_config.json")
# Erstelle den Ordner, falls er im Volume noch nicht existiert
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)



def save_dashboard_id(msg_id, channel_id):
    with open(DASHBOARD_FILE, "w") as f:
        json.dump({"message_id": msg_id, "channel_id": channel_id}, f)

def load_dashboard_id():
    if os.path.exists(DASHBOARD_FILE):
        with open(DASHBOARD_FILE, "r") as f:
            return json.load(f)
    return None

# Der Rest der Datenbank-Funktionen bleibt gleich:
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: 
            try: 
                data = json.load(f)
                # --- AUTO-FIX FÜR ALTE DATENSTRUKTUR ---
                updated = False
                for uid in data:
                    # Wenn 'chars' fehlt, ist es ein alter Eintrag
                    if "chars" not in data[uid]:
                        old_name = data[uid].get("name", "Unbekannt")
                        old_realm = data[uid].get("realm", "Unbekannt")
                        # Umwandeln in das neue Listen-Format
                        data[uid] = {"chars": [{"name": old_name, "realm": old_realm}]}
                        updated = True
                
                if updated:
                    save_db(data)
                    print("✅ Datenbank erfolgreich auf das neue Twink-Format aktualisiert.")
                return data
            except Exception as e:
                print(f"Fehler beim Laden der DB: {e}")
                return {}
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
        enchantable_slots = ['chest', 'legs', 'boots', 'mainhand', 'offhand', 'finger1', 'finger2', 'shoulders', 'head']
        
        for slot, info in items.items():
            if slot in enchantable_slots and info.get('enchant') is None:
                missing_enchant = True
            empty_sockets += info.get('gems_missing', 0)
            
        return {
            "ilvl": ilvl,
            "missing_enchant": missing_enchant,
            "empty_sockets": empty_sockets
        }

async def update_dashboard_logic():
    config = load_dashboard_id()
    if not config: return
    guild = bot.get_guild(SERVER_ID)
    channel = guild.get_channel(config['channel_id'])
    try: message = await channel.fetch_message(config['message_id'])
    except: return

    db = load_db()
    min_ilvl = 265
    
    # Listen für die Kategorien
    ready_chars = []
    not_ready_chars = []

    async with aiohttp.ClientSession() as session:
        for uid, data in db.items():
            member = guild.get_member(int(uid))
            if not member: continue
            
            for char in data.get('chars', []):
                res = await fetch_gear_data(session, char['realm'], char['name'])
                if res:
                    status_icon = "✅" if (res['ilvl'] >= min_ilvl and not res['missing_enchant']) else "⚠️"
                    line = f"{status_icon} **{char['name']}** ({res['class']}) - iLvl: {res['ilvl']}"
                    
                    if status_icon == "✅":
                        ready_chars.append(line)
                    else:
                        # Detail-Info warum nicht ready
                        reasons = []
                        if res['ilvl'] < min_ilvl: reasons.append(f"iLvl < {min_ilvl}")
                        if res['missing_enchant']: reasons.append("VZ fehlt")
                        not_ready_chars.append(f"{line} *({', '.join(reasons)})*")
                await asyncio.sleep(0.1) # Rate-Limit Schutz

    new_embed = discord.Embed(
        title="⚔️ RAID-READY DASHBOARD ⚔️",
        description=f"Letztes Update: <t:{int(datetime.now().timestamp())}:R>",
        color=0x2f3136 # Dunkles Design
    )

    if ready_chars:
        new_embed.add_field(name="🟢 EINSATZBEREIT", value="\n".join(ready_chars), inline=False)
    
    if not_ready_chars:
        new_embed.add_field(name="🔴 NOCH ARBEIT ERFORDERLICH", value="\n".join(not_ready_chars), inline=False)

    # Ein schönes Thumbnail vom Gildenwappen oder WoW Logo (optional)
    new_embed.set_thumbnail(url="https://i.imgur.com/8vW9X7S.png") 
    
    await message.edit(embed=new_embed)

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
        # HIER DARF NICHTS MIT .start() STEHEN!

    async def setup_hook(self):
        # 1. Deine Views registrieren
        self.add_view(GildenLeitungView())
        self.add_view(RaidPollView())
        
        # 2. Den Task starten (HIER ist es sicher!)
        if not self.archive_logs.is_running():
            self.archive_logs.start()
            print("Archiv-Task wurde erfolgreich gestartet.")
            
        # 3. Slash Commands synchronisieren
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

# In der setup_hook:
    if not self.refresh_dashboard.is_running():
        self.refresh_dashboard.start()

    @tasks.loop(minutes=30)
    async def refresh_dashboard(self):
        await update_dashboard_logic()

    @refresh_dashboard.before_loop
    async def before_refresh(self):
        await self.wait_until_ready()


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

@bot.tree.command(name="add_char", description="Fügt einem User einen Charakter (Main/Twink) hinzu")
async def add_char(interaction: discord.Interaction, user: discord.Member, rio_link: str):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("❌ Keine Rechte!", ephemeral=True)

    match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
    if not match: return await interaction.response.send_message("❌ Link ungültig!", ephemeral=True)

    realm, name = match.group(1).capitalize(), match.group(2).capitalize()
    db = load_db()
    uid = str(user.id)

    if uid not in db: db[uid] = {"chars": []}
    
    # Dubletten prüfen
    if any(c['name'] == name and c['realm'] == realm for c in db[uid]['chars']):
        return await interaction.response.send_message(f"⚠️ **{name}** ist bereits für {user.display_name} registriert.", ephemeral=True)

    db[uid]['chars'].append({"name": name, "realm": realm})
    save_db(db)
    await interaction.response.send_message(f"✅ **{name}-{realm}** wurde für {user.mention} hinzugefüga.")

@bot.tree.command(name="remove_char", description="Entfernt einen spezifischen Charakter eines Users")
async def remove_char(interaction: discord.Interaction, user: discord.Member, char_name: str):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles): return
    
    db = load_db()
    uid = str(user.id)
    if uid in db:
        initial_len = len(db[uid]['chars'])
        db[uid]['chars'] = [c for c in db[uid]['chars'] if c['name'].lower() != char_name.lower()]
        if len(db[uid]['chars']) < initial_len:
            save_db(db)
            return await interaction.response.send_message(f"🗑️ Charakter **{char_name}** für {user.display_name} gelöscht.")
    
    await interaction.response.send_message("❌ Charakter nicht gefunden.", ephemeral=True)

@bot.tree.command(name="list_members", description="Zeigt eine übersichtliche Liste aller Mitglieder")
async def list_members(interaction: discord.Interaction):
    db = load_db()
    if not db:
        return await interaction.response.send_message("Die Datenbank ist noch leer.")
    
    embed = discord.Embed(
        title="🛡️ Gilden-Datenbank | Mitglieder & Chars",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # Wir sortieren die IDs alphabetisch nach dem Discord-Namen für bessere Ordnung
    sorted_members = sorted(db.items(), key=lambda x: (interaction.guild.get_member(int(x[0])).display_name if interaction.guild.get_member(int(x[0])) else "Unbekannt"))

    for uid, data in sorted_members:
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"ID: {uid}"
        
        # Charaktere kompakt formatieren: "Name (Server), Name (Server)"
        chars = data.get("chars", [])
        if chars:
            char_text = "\n".join([f"🔹 {c['name']} - *{c['realm']}*" for c in chars])
        else:
            char_text = "❌ Keine Charaktere"

        # 'inline=True' sorgt dafür, dass Discord (wenn Platz ist) Spalten bildet
        embed.add_field(
            name=f"👤 {name}",
            value=char_text,
            inline=True 
        )

    # Ein kleiner Footer macht das Ganze professioneller
    embed.set_footer(text=f"Gesamtanzahl Spieler: {len(db)}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="check_raid_ready", description="Prüft alle Charaktere auf Gear und Enchants")
async def check_raid_ready(interaction: discord.Interaction, min_ilvl: int = 270):
    await interaction.response.defer()
    db = load_db()
    rr_role = interaction.guild.get_role(RAID_READY_ROLLE_ID)
    
    results = []
    async with aiohttp.ClientSession() as session:
        for uid, data in db.items():
            member = interaction.guild.get_member(int(uid))
            if not member: continue
            
            player_ready = False
            char_statuses = []

            for char in data['chars']:
                res = await fetch_gear_data(session, char['realm'], char['name'])
                if res:
                    warns = []
                    if res['ilvl'] < min_ilvl: warns.append(f"iLvl {res['ilvl']}")
                    if res['missing_enchant']: warns.append("Enchants")
                    if res['empty_sockets'] > 0: warns.append(f"{res['empty_sockets']} Sockets")
                    
                    if not warns:
                        player_ready = True
                        char_statuses.append(f"✅ **{char['name']}**: Ready")
                    else:
                        char_statuses.append(f"❌ **{char['name']}**: Fehlt: {', '.join(warns)}")
                await asyncio.sleep(0.2)

            # Rollen-Vergabe: Wenn MINDESTENS EIN Charakter ready ist
            try:
                if player_ready:
                    if rr_role and rr_role not in member.roles: await member.add_roles(rr_role)
                else:
                    if rr_role and rr_role in member.roles: await member.remove_roles(rr_role)
            except: pass

            results.append(f"**{member.display_name}**:\n" + "\n".join(char_statuses))

    full_text = "\n\n".join(results)
    # Falls der Text zu lang für ein Embed ist, in mehrere Teile splitten
    if len(full_text) > 4000:
        await interaction.followup.send("Ergebnis ist zu lang für Discord, bitte iLvl Check verfeinern.")
    else:
        await interaction.followup.send(embed=discord.Embed(title="Raid-Ready Check", description=full_text, color=discord.Color.blue()))

@bot.tree.command(name="whois", description="Zeigt alle Charaktere eines bestimmten Users")
async def whois(interaction: discord.Interaction, user: discord.Member):
    db = load_db()
    uid = str(user.id)
    if uid not in db or not db[uid]["chars"]:
        return await interaction.response.send_message(f"{user.display_name} hat keine registrierten Charaktere.", ephemeral=True)
    
    chars = "\n".join([f"✅ {c['name']} ({c['realm']})" for c in db[uid]["chars"]])
    embed = discord.Embed(title=f"Charaktere von {user.display_name}", description=chars, color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

bot.tree.command(name="setup_dashboard", description="Erstellt das Live-Gear-Dashboard")
async def setup_dashboard(interaction: discord.Interaction):
    if not any(role.id == OFFIZIER_ROLLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("❌ Keine Rechte!", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(title="📊 Raid-Ready Live-Dashboard", description="Initialisierung läuft...", color=discord.Color.gold())
    msg = await interaction.channel.send(embed=embed)
    
    save_dashboard_id(msg.id, interaction.channel_id)
    await interaction.followup.send("✅ Dashboard erstellt und verknüpft!")
    # Sofort das erste Update triggern
    await update_dashboard_logic()
    
bot.run(os.getenv('DISCORD_TOKEN'))
