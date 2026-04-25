import os
import json
import discord
import asyncio
import aiohttp
import re
from quart import Quart, render_template_string, redirect, url_for, request
from datetime import datetime

app = Quart(__name__)

# Konfiguration aus Railway-Variablen
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)

bot_instance = None

# --- HILFSFUNKTIONEN ---

def parse_rio_link(link):
    match = re.search(r'characters/eu/([^/]+)/([^/]+)', link)
    if match:
        realm = match.group(1).replace('-', ' ').title()
        name = match.group(2).title()
        return name, realm
    return None, None

async def fetch_char_data(name, realm):
    clean_name = name.strip().lower()
    clean_realm = realm.strip().lower().replace(" ", "-")
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={clean_realm}&name={clean_name}&fields=gear"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "ilvl": data.get('gear', {}).get('item_level_equipped', 0),
                        "class": data.get('class', 'Unbekannt'),
                        "spec": data.get('active_spec_name', 'Unbekannt'),
                        "rio_url": f"https://raider.io/characters/eu/{clean_realm}/{clean_name}"
                    }
    except: pass
    return {"ilvl": "??", "class": "Unbekannt", "spec": "Unbekannt", "rio_url": f"https://raider.io/characters/eu/{clean_realm}/{clean_name}"}

# --- DISCORD INTERAKTION (BUTTONS) ---

class ActionButtons(discord.ui.View):
    def __init__(self, applicant_id=None, char_name=None):
        super().__init__(timeout=None) # WICHTIG für dauerhafte Buttons
        self.applicant_id = applicant_id
        self.char_name = char_name

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.green, custom_id="btn_accept", emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        if member:
            role_mitglied = guild.get_role(MITGLIED_ROLLE_ID)
            role_bewerber = guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if role_bewerber in member.roles: await member.remove_roles(role_bewerber)
                await member.add_roles(role_mitglied)
                await interaction.response.send_message(f"✅ **{self.char_name}** wurde als Mitglied aufgenommen!", ephemeral=False)
                self.stop()
            except Exception as e: await interaction.response.send_message(f"Fehler: {e}", ephemeral=True)
        else: await interaction.response.send_message("User nicht gefunden.", ephemeral=True)

    @discord.ui.button(label="Ablehnen", style=discord.ButtonStyle.red, custom_id="btn_decline", emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        if member:
            role_bewerber = guild.get_role(BEWERBER_ROLLE_ID)
            role_gast = guild.get_role(GAST_ROLLE_ID)
            try:
                if role_bewerber in member.roles: await member.remove_roles(role_bewerber)
                await member.add_roles(role_gast)
                await interaction.response.send_message(f"❌ Bewerbung von **{self.char_name}** abgelehnt. Status: Gast.", ephemeral=False)
                self.stop()
            except Exception as e: await interaction.response.send_message(f"Fehler: {e}", ephemeral=True)

# --- WEB DASHBOARD ---

@app.route('/')
async def index():
    members_data = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: members_data = json.load(f)
            except: pass

    guild = bot_instance.get_guild(SERVER_ID) if bot_instance and bot_instance.is_ready() else None
    
    # Vorbereitung der Listen
    mains = []
    twinks_by_main = {}

    for uid, user_data in members_data.items():
        # Basis-Daten abrufen (wie in deinem Original)
        role_info = {"name": "Gast", "color": "slate", "priority": 4}
        display_name = user_data.get("name", f"User {uid}")
        
        if guild:
            member = guild.get_member(int(uid))
            if member:
                display_name = member.display_name
                role_ids = [r.id for r in member.roles]
                if OFFIZIER_ROLLE_ID in role_ids: role_info = {"name": "Offizier", "color": "violet", "priority": 1}
                elif MITGLIED_ROLLE_ID in role_ids: role_info = {"name": "Mitglied", "color": "emerald", "priority": 2}
                elif BEWERBER_ROLLE_ID in role_ids: role_info = {"name": "Bewerber", "color": "amber", "priority": 3}

        # Charakter-Daten von RIO laden
        processed_chars = []
        # Wir unterstützen beide Formate: Die alte "chars"-Liste und das neue Format
        char_list = user_data.get("chars", [])
        if not char_list and "rio_url" in user_data: # Falls es ein neuer Twink-Eintrag ist
             char_list = [{"name": user_data["name"], "realm": user_data.get("realm", "Blackhand"), "rio_url": user_data["rio_url"]}]

        for char in char_list:
            live = await fetch_char_data(char['name'], char.get('realm', 'Blackhand'))
            char.update(live)
            processed_chars.append(char)

        user_info = {
            "uid": uid, 
            "name": display_name, 
            "chars": processed_chars, 
            "role": role_info,
            "is_twink": user_data.get("is_twink", False)
        }

        # Einsortieren
        if user_info["is_twink"]:
            main_id = user_data.get("main_account_id")
            if main_id not in twinks_by_main: twinks_by_main[main_id] = []
            twinks_by_main[main_id].append(user_info)
        else:
            mains.append(user_info)

    mains.sort(key=lambda x: x['role']['priority'])

    # Das Template (hier gekürzt, siehe unten für das vollständige HTML)
    return await render_template_string(html_template, mains=mains, twinks_by_main=twinks_by_main)

@app.route('/add_applicant', methods=['POST'])
async def add_applicant():
    form = await request.form
    rio_link = form.get('rio_link', '').strip()
    discord_id = form.get('discord_id', '').strip()
    if not rio_link or not discord_id: return redirect('/')
    
    name, realm = parse_rio_link(rio_link)
    if not name: return redirect('/')
    data = await fetch_char_data(name, realm)
    
    if bot_instance and bot_instance.is_ready():
        guild = bot_instance.get_guild(SERVER_ID)
        member = guild.get_member(int(discord_id))
        
        # 1. Rollen-Wechsel: Gast weg -> Bewerber her
        if member:
            role_gast = guild.get_role(GAST_ROLLE_ID)
            role_bewerber = guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if role_gast in member.roles: await member.remove_roles(role_gast)
                await member.add_roles(role_bewerber)
            except: pass

        # 2. Forum Post erstellen (Exakt wie im Bild)
        forum_channel = bot_instance.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            # Haupt-Embed
            embed = discord.Embed(title=f"🛡️ Neuer Eintrag: {name}", color=0x3498db)
            embed.add_field(name="Klasse/Spec", value=f"{data['class']} ({data['spec']})", inline=False)
            embed.add_field(name="Spieler", value=f"{member.display_name if member else 'Unbekannt'}", inline=False)
            embed.add_field(name="Server", value=realm, inline=False)
            embed.add_field(name="Eintrittsdatum", value=datetime.now().strftime("%d.%m.%Y"), inline=False)
            
            # Detail-Embed (Das lila Feld aus dem Screenshot)
            embed_detail = discord.Embed(title=f"Aktualisierter Eintrag: {name}", color=0x9b59b6)
            embed_detail.add_field(name="Klasse / Spec", value=f"{data['class']} ({data['spec']})", inline=True)
            embed_detail.add_field(name="Item-Level", value=str(data['ilvl']), inline=True)
            embed_detail.add_field(name="Link", value=f"🔗 [Rio]({rio_link})", inline=False)

            # Entscheidung-View
            view = ActionButtons(discord_id, name)

            await forum_channel.create_thread(
                name=f"Bewerbung: {name} ({data['class']})",
                embeds=[embed, embed_detail],
                content=f"🔗 [Raider.io Profile]({rio_link})\n📊 [Warcraftlogs Profile](https://www.warcraftlogs.com/character/eu/{realm.replace(' ', '-').lower()}/{name.lower()})",
                view=view
            )
            
            # Button-Nachricht unter den Thread posten (optional für Optik)
            # await thread.send("💡 **Entscheidung treffen:**", view=view)

    # 3. In Datenbank speichern
    with open(DB_FILE, "r+", encoding="utf-8") as f:
        try: db = json.load(f)
        except: db = {}
        if discord_id not in db: db[discord_id] = {"chars": []}
        db[discord_id]["chars"].append({"name": name, "realm": realm})
        f.seek(0); json.dump(db, f, indent=4, ensure_ascii=False); f.truncate()

    return redirect('/')

@app.route('/delete/<uid>/<int:char_idx>')
async def delete_char(uid, char_idx):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: db = json.load(f)
            except: db = {}
        if uid in db:
            db[uid]["chars"].pop(char_idx)
            if not db[uid]["chars"]: del db[uid]
            with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db, f, indent=4, ensure_ascii=False)
    return redirect('/')

async def run_web(bot=None):
    global bot_instance
    bot_instance = bot
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)