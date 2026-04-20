import os
import json
import discord
import asyncio
import aiohttp
import re
from quart import Quart, render_template_string, redirect, url_for, request
from datetime import datetime

app = Quart(__name__)

# Pfade & IDs
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)

bot_instance = None

# Hilfsfunktion: Analysiert den Raider.io Link (für das Formular)
def parse_rio_link(link):
    match = re.search(r'characters/eu/([^/]+)/([^/]+)', link)
    if match:
        realm = match.group(1).replace('-', ' ').title()
        name = match.group(2).title()
        return name, realm
    return None, None

# Hilfsfunktion: Holt iLvl und Klasse live von Raider.io
async def fetch_char_data(name, realm):
    clean_name = name.strip().lower()
    clean_realm = realm.strip().lower().replace(" ", "-")
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={clean_realm}&name={clean_name}&fields=gear"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "ilvl": data.get('gear', {}).get('item_level_equipped', 0),
                        "class": data.get('class', 'Unbekannt'),
                        "rio_url": f"https://raider.io/characters/eu/{clean_realm}/{clean_name}"
                    }
    except: pass
    # Fallback falls API down oder Charakter nicht gefunden
    return {
        "ilvl": "??", 
        "class": "Unbekannt", 
        "rio_url": f"https://raider.io/characters/eu/{clean_realm}/{clean_name}"
    }

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
        role_info = {"name": "Gast", "color": "slate", "priority": 4}
        display_name = f"User {uid}"
        
        if guild:
            try:
                member = guild.get_member(int(uid))
                if member:
                    display_name = member.display_name
                    role_ids = [r.id for r in member.roles]
                    if OFFIZIER_ROLLE_ID in role_ids: role_info = {"name": "Offizier", "color": "violet", "priority": 1}
                    elif MITGLIED_ROLLE_ID in role_ids: role_info = {"name": "Mitglied", "color": "emerald", "priority": 2}
                    elif BEWERBER_ROLLE_ID in role_ids: role_info = {"name": "Bewerber", "color": "amber", "priority": 3}
            except: pass

        # Verarbeite alle Charaktere dieses Users LIVE
        processed_chars = []
        for char in user_data.get("chars", []):
            live_data = await fetch_char_data(char['name'], char.get('realm', 'Blackhand'))
            char_copy = char.copy()
            char_copy.update(live_data) # Aktualisiert ilvl, class und rio_url live
            processed_chars.append(char_copy)

        enhanced_list.append({
            "uid": uid, 
            "name": display_name, 
            "chars": processed_chars, 
            "role": role_info
        })

    enhanced_list.sort(key=lambda x: x['role']['priority'])

    html_template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background: #0b1120; }
            .glass { background: rgba(30, 41, 59, 0.4); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.05); }
        </style>
        <title>Gilden Live-Dashboard</title>
    </head>
    <body class="text-slate-200 p-4 md:p-10">
        <div class="container mx-auto max-w-6xl">
            
            <div class="glass p-8 rounded-3xl mb-12 shadow-2xl">
                <h1 class="text-3xl font-black italic uppercase text-white mb-6">Gilden<span class="text-indigo-500">Dashboard</span> <span class="text-xs font-mono text-slate-500 bg-slate-800 px-2 py-1 rounded">LIVE SYNC</span></h1>
                <form action="/add_applicant" method="post" class="flex flex-col md:flex-row gap-4">
                    <input name="rio_link" placeholder="Raider.io Link einfügen..." class="flex-grow bg-slate-900/50 border border-slate-700 px-4 py-3 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-white" required>
                    <input name="discord_id" placeholder="Discord ID" class="md:w-1/4 bg-slate-900/50 border border-slate-700 px-4 py-3 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-white" required>
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-8 py-3 rounded-xl transition-all">Hinzufügen</button>
                </form>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {% for user in members_list %}
                <div class="glass rounded-3xl p-6 border-l-4 border-{{user.role.color}}-500 shadow-xl relative transition-all hover:scale-[1.01]">
                    <div class="absolute top-4 right-4">
                        <span class="px-3 py-1 bg-{{user.role.color}}-500/10 text-{{user.role.color}}-400 text-[10px] font-bold rounded-full border border-{{user.role.color}}-500/20 uppercase tracking-widest">{{user.role.name}}</span>
                    </div>
                    <h2 class="text-2xl font-black text-white mb-6 tracking-tight">{{user.name}}</h2>
                    
                    <div class="space-y-4">
                        {% for char in user.chars %}
                        <div class="bg-slate-950/40 p-4 rounded-2xl border border-slate-800/50">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="font-bold text-slate-100 text-lg leading-none mb-1">{{char.name}}</p>
                                    <p class="text-[10px] text-indigo-400 font-black uppercase mb-2">{{char.class}}</p>
                                    <a href="{{char.rio_url}}" target="_blank" class="text-[10px] bg-orange-600/20 text-orange-400 px-2 py-1 rounded font-bold hover:bg-orange-600/40 transition-all">RAIDER.IO ↗</a>
                                </div>
                                <div class="text-right">
                                    <p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">iLvl</p>
                                    <p class="text-3xl font-black text-white font-mono leading-none">{{char.ilvl}}</p>
                                </div>
                            </div>
                            <div class="mt-4 pt-3 border-t border-slate-800/50 flex justify-end">
                                <a href="/delete/{{user.uid}}/{{loop.index0}}" class="text-slate-700 hover:text-red-500 text-sm transition-colors" onclick="return confirm('Löschen?')">🗑️ Entfernen</a>
                            </div>
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

# Route zum Hinzufügen (Logik wie zuvor, nutzt Link-Parsing)
@app.route('/add_applicant', methods=['POST'])
async def add_applicant():
    form = await request.form
    rio_link = form.get('rio_link', '').strip()
    discord_id = form.get('discord_id', '').strip()
    
    if not rio_link or not discord_id: return redirect('/')
    name, realm = parse_rio_link(rio_link)
    if not name or not realm: return redirect('/')

    # Kurz-Abfrage für den Forum Post
    data = await fetch_char_data(name, realm)
    
    if bot_instance and bot_instance.is_ready():
        forum_channel = bot_instance.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            content = f"**Neue Bewerbung!**\n👤 <@{discord_id}>\n⚔️ {name}-{realm}\n🛡️ {data['class']}\n📈 iLvl: {data['ilvl']}\n\n[Profil]({rio_link})"
            await forum_channel.create_thread(name=f"Bewerbung: {name}", content=content)

    # In DB speichern
    with open(DB_FILE, "r+", encoding="utf-8") as f:
        try: db = json.load(f)
        except: db = {}
        if discord_id not in db: db[discord_id] = {"chars": []}
        db[discord_id]["chars"].append({"name": name, "realm": realm}) # Nur Basisdaten, Live-Fetch im index
        f.seek(0); json.dump(db, f, indent=4, ensure_ascii=False); f.truncate()

    return redirect('/')

# (Lösch-Funktion und run_web wie gehabt)
@app.route('/delete/<uid>/<int:char_idx>')
async def delete_char(uid, char_idx):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        if uid in db:
            db[uid]["chars"].pop(char_idx)
            if not db[uid]["chars"]: del db[uid]
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