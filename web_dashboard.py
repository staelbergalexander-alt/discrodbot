import os
import json
import discord
import asyncio
import aiohttp
from quart import Quart, render_template_string, redirect, url_for, request
from datetime import datetime

app = Quart(__name__)

# Pfade & IDs
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0) # NEU: Deine Forum-ID
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)

bot_instance = None

async def fetch_real_ilvl(name, realm):
    clean_name = name.strip().lower()
    clean_realm = realm.strip().lower().replace(" ", "-")
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={clean_realm}&name={clean_name}&fields=gear"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('gear', {}).get('item_level_equipped', 0), data.get('class'), data.get('active_spec_name')
    except: pass
    return None, None, None

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
        display_name = f"User {uid[-4:]}"
        joined_date = None
        if guild:
            member = guild.get_member(int(uid))
            if member:
                display_name = member.display_name
                joined_date = member.joined_at.strftime("%d.%m.%Y") if member.joined_at else None
                role_ids = [r.id for r in member.roles]
                if OFFIZIER_ROLLE_ID in role_ids: role_info = {"name": "Offizier", "color": "violet", "priority": 1}
                elif MITGLIED_ROLLE_ID in role_ids: role_info = {"name": "Mitglied", "color": "emerald", "priority": 2}
                elif BEWERBER_ROLLE_ID in role_ids: role_info = {"name": "Bewerber", "color": "amber", "priority": 3}

        enhanced_list.append({"uid": uid, "name": display_name, "chars": user_data.get("chars", []), "role": role_info, "joined_at": joined_date})

    enhanced_list.sort(key=lambda x: x['role']['priority'])

    html_template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
        <style>body { font-family: 'Inter', sans-serif; background: #0b1120; }</style>
        <title>Gilden Dashboard</title>
    </head>
    <body class="text-slate-200 p-4 md:p-10">
        <div class="container mx-auto max-w-6xl">
            
            <div class="flex flex-col md:flex-row justify-between items-center mb-12 gap-6 bg-slate-900/50 p-8 rounded-3xl border border-slate-800">
                <div>
                    <h1 class="text-4xl font-black italic uppercase text-white">Gilden<span class="text-indigo-500">Admin</span></h1>
                    <p class="text-slate-500 text-sm">Bewerber hinzufügen & Discord Forum erstellen</p>
                </div>
                
                <form action="/add_applicant" method="post" class="flex flex-wrap gap-3">
                    <input name="name" placeholder="Char Name" class="bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl focus:outline-none focus:border-indigo-500 transition-all text-white" required>
                    <input name="realm" placeholder="Server (z.B. Blackhand)" class="bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl focus:outline-none focus:border-indigo-500 transition-all text-white" required>
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-6 py-2 rounded-xl transition-all shadow-lg shadow-indigo-500/20">+ Hinzufügen</button>
                </form>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {% for user in members_list %}
                <div class="bg-slate-900/40 rounded-3xl p-6 border border-slate-800 relative hover:border-{{user.role.color}}-500/30 transition-all">
                    <div class="absolute top-4 right-4 text-right">
                        <span class="px-2 py-0.5 bg-{{user.role.color}}-500/10 text-{{user.role.color}}-400 text-[10px] font-bold rounded-full border border-{{user.role.color}}-500/20 uppercase tracking-widest">{{user.role.name}}</span>
                    </div>
                    <h2 class="text-xl font-bold text-white mb-4">{{user.name}}</h2>
                    <div class="space-y-3">
                        {% for char in user.chars %}
                        <div class="bg-slate-950/50 p-3 rounded-2xl border border-slate-800 flex justify-between items-center group">
                            <div>
                                <p class="font-bold text-slate-200">{{char.name}}</p>
                                <p class="text-[10px] text-indigo-400 font-bold uppercase">{{char.class}} ({{char.ilvl}})</p>
                            </div>
                            <a href="/delete/{{user.uid}}/{{loop.index0}}" class="text-slate-800 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100">🗑️</a>
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
    name = form.get('name')
    realm = form.get('realm')
    
    if not name or not realm: return redirect('/')

    # 1. Daten von Raider.io holen
    ilvl, char_class, spec = await fetch_real_ilvl(name, realm)
    
    # 2. Discord Forum Post erstellen
    if bot_instance and bot_instance.is_ready():
        forum_channel = bot_instance.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            content = f"**Neue Bewerbung eingegangen!**\n\n**Name:** {name}\n**Server:** {realm}\n**Klasse:** {char_class or 'Unbekannt'}\n**iLvl:** {ilvl or '?'}\n\n[Raider.io Profil](https://raider.io/characters/eu/{realm.replace(' ', '-').lower()}/{name.lower()})"
            # Thread im Forum erstellen
            await forum_channel.create_thread(name=f"Bewerbung: {name} ({char_class or '?'})", content=content)

    # 3. In Datenbank speichern (als neuer Gast/Bewerber ohne Discord-Verknüpfung)
    # Hier nutzen wir den Namen als temporäre ID, falls kein Discord-User verknüpft ist
    temp_id = f"manual_{name.lower()}"
    
    with open(DB_FILE, "r+", encoding="utf-8") as f:
        data = json.load(f)
        new_char = {"name": name, "realm": realm, "class": char_class or "Unbekannt", "ilvl": ilvl or 0}
        if temp_id not in data: data[temp_id] = {"chars": []}
        data[temp_id]["chars"].append(new_char)
        f.seek(0)
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.truncate()

    return redirect('/')

# (Restliche Funktionen wie delete_char und run_web bleiben gleich)
@app.route('/delete/<uid>/<int:char_idx>')
async def delete_char(uid, char_idx):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if uid in data:
            data[uid]["chars"].pop(char_idx)
            if not data[uid]["chars"]: del data[uid]
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
    return redirect('/')

async def run_web(bot=None):
    global bot_instance
    bot_instance = bot
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)