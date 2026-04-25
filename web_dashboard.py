import os
import json
import discord
import asyncio
import aiohttp
import re
from quart import Quart, render_template_string, redirect, url_for, request
from datetime import datetime

app = Quart(__name__)

# Konfiguration aus Railway-Variablen oder lokal
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
    """Extrahiert Name und Server aus einem Raider.io Link."""
    match = re.search(r'characters/eu/([^/]+)/([^/]+)', link)
    if match:
        realm = match.group(1).replace('-', ' ').title()
        name = match.group(2).title()
        return name, realm
    return None, None

async def fetch_char_data(name, realm):
    """Holt Live-Daten von der Raider.io API."""
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
        super().__init__(timeout=None)
        self.applicant_id = int(applicant_id)
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
                await interaction.response.send_message(f"✅ **{self.char_name}** wurde aufgenommen!", ephemeral=False)
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
                await interaction.response.send_message(f"❌ Bewerbung von **{self.char_name}** abgelehnt.", ephemeral=False)
            except Exception as e: await interaction.response.send_message(f"Fehler: {e}", ephemeral=True)

# --- WEB DASHBOARD ---

@app.route('/')
async def index():
    members_data = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: members_data = json.load(f)
            except: pass

    enhanced_list = []
    guild = bot_instance.get_guild(SERVER_ID) if bot_instance and bot_instance.is_ready() else None

    for uid, user_data in members_data.items():
        # Standard-Rolle (Gast)
        role_info = {"name": "Gast", "color": "slate", "priority": 4}
        display_name = f"User {uid}"
        
        if guild:
            member = guild.get_member(int(uid))
            if member:
                display_name = member.display_name
                role_ids = [r.id for r in member.roles]
                if OFFIZIER_ROLLE_ID in role_ids: role_info = {"name": "Offizier", "color": "violet", "priority": 1}
                elif MITGLIED_ROLLE_ID in role_ids: role_info = {"name": "Mitglied", "color": "emerald", "priority": 2}
                elif BEWERBER_ROLLE_ID in role_ids: role_info = {"name": "Bewerber", "color": "amber", "priority": 3}

        # Charaktere verarbeiten
        processed_chars = []
        char_list = user_data.get("chars", [])
        
        # Falls es ein alter Einzeleintrag ist, in Liste umwandeln
        if not char_list and user_data.get("name"):
            char_list = [{"name": user_data["name"], "realm": user_data.get("realm", "Blackhand")}]

        for char in char_list:
            live = await fetch_char_data(char['name'], char.get('realm', 'Blackhand'))
            char.update(live)
            processed_chars.append(char)

        enhanced_list.append({
            "uid": uid, 
            "name": display_name, 
            "chars": processed_chars, 
            "role": role_info
        })

    # Sortieren nach Rang-Priorität
    enhanced_list.sort(key=lambda x: x['role']['priority'])

    html_template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background: #0b1120; scroll-behavior: smooth; }
            .card-gradient { background: linear-gradient(135deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.8) 100%); }
        </style>
        <title>Gilden Dashboard</title>
    </head>
    <body class="text-slate-200 p-4 md:p-10">
        <div class="container mx-auto max-w-6xl">
            <div class="bg-slate-900/60 p-6 md:p-8 rounded-3xl border border-slate-800 mb-10 shadow-2xl backdrop-blur-md">
                <h1 class="text-3xl font-black italic uppercase text-white mb-6 tracking-tighter">Gilden<span class="text-indigo-500">Admin</span></h1>
                <form action="/add_applicant" method="post" class="flex flex-col md:flex-row gap-4">
                    <input name="rio_link" placeholder="Raider.io Profil Link..." class="flex-grow bg-slate-800 border border-slate-700 px-4 py-3 rounded-xl outline-none focus:border-indigo-500 text-white transition-all shadow-inner" required>
                    <input name="discord_id" placeholder="Discord ID" class="md:w-1/4 bg-slate-800 border border-slate-700 px-4 py-3 rounded-xl outline-none focus:border-indigo-500 text-white transition-all shadow-inner" required>
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-8 py-3 rounded-xl transition-all shadow-lg shadow-indigo-500/20 uppercase text-sm tracking-widest">Hinzufügen</button>
                </form>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {% for user in members_list %}
                <div class="card-gradient rounded-3xl p-6 border border-slate-800 relative group transition-all hover:border-indigo-500/50 shadow-xl">
                    <div class="absolute top-4 right-4">
                        <span class="px-3 py-1 bg-{{user.role.color}}-500/10 text-{{user.role.color}}-400 text-[10px] font-bold rounded-full border border-{{user.role.color}}-500/20 uppercase tracking-widest">
                            {{user.role.name}}
                        </span>
                    </div>

                    <h2 class="text-xl font-bold text-white mb-5 flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-{{user.role.color}}-500"></span>
                        {{user.name}}
                    </h2>

                    <div class="space-y-3">
                        {% for char in user.chars %}
                        <div class="bg-slate-950/50 p-4 rounded-2xl border border-slate-800 flex justify-between items-center transition-all hover:bg-slate-900 group/char">
                            <div class="flex-grow">
                                <div class="flex items-center gap-2">
                                    <p class="font-bold text-slate-100">{{char.name}}</p>
                                    <span class="text-[9px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400 uppercase">{{char.spec}}</span>
                                </div>
                                <p class="text-[10px] text-indigo-400 font-bold uppercase tracking-tight mt-1">
                                    {{char.class}} • <span class="text-white">{{char.ilvl}} iLvl</span>
                                </p>
                                <a href="{{char.rio_url}}" target="_blank" class="text-[9px] text-orange-500 font-black hover:text-orange-400 transition-colors mt-2 inline-block">RAIDER.IO ↗</a>
                            </div>
                            <a href="/delete/{{user.uid}}/{{loop.index0}}" 
                               class="ml-2 text-slate-700 hover:text-red-500 transition-all opacity-0 group-hover/char:opacity-100" 
                               onclick="return confirm('Charakter {{char.name}} wirklich entfernen?')">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                            </a>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    """
    return await render_template_string(html_template, members_list=enhanced_list)

@app.route('/add_applicant', methods=['POST'])
async def add_applicant():
    form = await request.form
    rio_link = form.get('rio_link', '').strip()
    discord_id = form.get('discord_id', '').strip()
    
    if not rio_link or not discord_id: return redirect('/')
    
    name, realm = parse_rio_link(rio_link)
    if not name: return redirect('/')
    
    data = await fetch_char_data(name, realm)
    
    # Discord Logik (Rollen & Forum)
    if bot_instance and bot_instance.is_ready():
        guild = bot_instance.get_guild(SERVER_ID)
        member = guild.get_member(int(discord_id))
        
        if member:
            role_gast = guild.get_role(GAST_ROLLE_ID)
            role_bewerber = guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if role_gast in member.roles: await member.remove_roles(role_gast)
                await member.add_roles(role_bewerber)
            except: pass

        forum_channel = bot_instance.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            embed = discord.Embed(title=f"🛡️ Neue Bewerbung: {name}", color=0x3498db, timestamp=datetime.now())
            embed.add_field(name="Charakter", value=f"**{name}** - {data['class']} ({data['spec']})", inline=False)
            embed.add_field(name="Item-Level", value=str(data['ilvl']), inline=True)
            embed.add_field(name="Server", value=realm, inline=True)
            embed.add_field(name="Spieler", value=member.mention if member else discord_id, inline=False)
            
            view = ActionButtons(discord_id, name)
            content = f"🔗 [Raider.io Profile]({rio_link})\n📊 [Warcraftlogs](https://www.warcraftlogs.com/character/eu/{realm.replace(' ', '-').lower()}/{name.lower()})"
            
            await forum_channel.create_thread(name=f"Bewerbung: {name}", embeds=[embed], content=content, view=view)

    # In JSON speichern (Gruppiert nach Discord ID)
    with open(DB_FILE, "r+", encoding="utf-8") as f:
        try: db = json.load(f)
        except: db = {}
        
        if discord_id not in db:
            db[discord_id] = {"chars": []}
        
        # Dubletten-Check
        if not any(c['name'] == name for c in db[discord_id]["chars"]):
            db[discord_id]["chars"].append({"name": name, "realm": realm})
            
        f.seek(0)
        json.dump(db, f, indent=4, ensure_ascii=False)
        f.truncate()

    return redirect('/')

@app.route('/delete/<uid>/<int:char_idx>')
async def delete_char(uid, char_idx):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: db = json.load(f)
            except: db = {}
            
        if uid in db:
            if 0 <= char_idx < len(db[uid]["chars"]):
                db[uid]["chars"].pop(char_idx)
                if not db[uid]["chars"]: 
                    del db[uid]
                
                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(db, f, indent=4, ensure_ascii=False)
                    
    return redirect('/')

async def run_web(bot=None):
    global bot_instance
    bot_instance = bot
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)