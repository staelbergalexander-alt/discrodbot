import os
import json
import discord
import asyncio
from quart import Quart, render_template_string, redirect, url_for
from datetime import datetime

app = Quart(__name__)

# Pfade & IDs (werden aus Railway-Variablen oder lokal geladen)
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)

# Globaler Bot-Speicher
bot_instance = None

@app.route('/')
async def index():
    members_data = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    members_data = json.loads(content)
        except Exception as e:
            print(f"Fehler beim Laden der JSON: {e}")

    enhanced_list = []
    total_chars = 0
    
    # SICHERHEITS-CHECK: Ist der Bot bereit?
    guild = None
    if bot_instance is not None and bot_instance.is_ready():
        guild = bot_instance.get_guild(SERVER_ID)

    for uid, user_data in members_data.items():
        # Standard-Rolle (Gast), Priorität 4 (niedrigste)
        role_info = {"name": "Gast", "color": "slate", "priority": 4}
        display_name = f"User {uid[-4:]}" # Fallback
        joined_date = None
        
        if guild:
            member = guild.get_member(int(uid))
            if member:
                display_name = member.display_name
                if member.joined_at:
                    joined_date = member.joined_at.strftime("%d.%m.%Y")
                
                role_ids = [r.id for r in member.roles]
                if OFFIZIER_ROLLE_ID in role_ids:
                    role_info = {"name": "Offizier", "color": "violet", "priority": 1}
                elif MITGLIED_ROLLE_ID in role_ids:
                    role_info = {"name": "Mitglied", "color": "emerald", "priority": 2}
                elif BEWERBER_ROLLE_ID in role_ids:
                    role_info = {"name": "Bewerber", "color": "amber", "priority": 3}

        enhanced_list.append({
            "uid": uid,
            "name": display_name,
            "chars": user_data.get("chars", []),
            "role": role_info,
            "joined_at": joined_date
        })
        total_chars += len(user_data.get("chars", []))

    # Sortierung: Offizier -> Mitglied -> Bewerber
    enhanced_list.sort(key=lambda x: x['role']['priority'])

    stats = {"total_members": len(members_data), "total_chars": total_chars}

    html_template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
        <title>Gilden Dashboard</title>
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #0b1120; }
            .glass { background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.05); }
            .char-card:hover .delete-btn { opacity: 1; }
        </style>
    </head>
    <body class="text-slate-200 min-h-screen pb-24">
        
        <header class="p-6 md:p-10 border-b border-slate-800 bg-[#0f172a] shadow-xl mb-12">
            <div class="container mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
                <div class="flex items-center gap-4">
                    <span class="text-4xl">🛡️</span>
                    <div>
                        <h1 class="text-3xl font-black tracking-tighter text-white uppercase italic">Gilden<span class="text-indigo-500">Dashboard</span></h1>
                        <p class="text-xs text-slate-500 font-mono">Real-time Member Overview</p>
                    </div>
                </div>
                
                <div class="flex items-center gap-3">
                    <div class="px-5 py-2 glass rounded-2xl text-center">
                        <p class="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Spieler</p>
                        <p class="text-xl font-black text-indigo-400">{{ stats.total_members }}</p>
                    </div>
                    <div class="px-5 py-2 glass rounded-2xl text-center">
                        <p class="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Charaktere</p>
                        <p class="text-xl font-black text-emerald-400">{{ stats.total_chars }}</p>
                    </div>
                </div>
            </div>
        </header>

        <main class="container mx-auto px-4">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                
                {% for user in members_list %}
                <div class="glass rounded-3xl p-6 shadow-2xl relative overflow-hidden transition-transform hover:scale-[1.02] hover:border-{{ user.role.color }}-500/30">
                    
                    <div class="absolute top-4 right-4 text-right">
                        <span class="px-3 py-1 bg-{{ user.role.color }}-950/50 border border-{{ user.role.color }}-500/30 text-{{ user.role.color }}-300 text-[10px] font-bold rounded-full uppercase tracking-widest">
                            {{ user.role.name }}
                        </span>
                        {% if user.role.name == "Bewerber" and user.joined_at %}
                        <p class="text-[9px] text-slate-600 mt-1 font-mono">Seit {{ user.joined_at }}</p>
                        {% endif %}
                    </div>

                    <div class="mb-6 pb-4 border-b border-slate-800">
                        <h2 class="text-2xl font-extrabold text-white tracking-tight">{{ user.name }}</h2>
                        <p class="text-[10px] font-mono text-slate-600 uppercase">UID: ...{{ user.uid[-6:] }}</p>
                    </div>

                    <div class="space-y-4">
                        {% if user.chars %}
                            {% for char in user.chars %}
                            <div class="char-card bg-[#0f172a] rounded-2xl p-4 border border-slate-800 relative transition-colors hover:border-indigo-500/20">
                                <div class="flex justify-between items-start gap-4">
                                    <div class="flex-grow">
                                        <div class="flex items-center gap-2 mb-1">
                                            <h3 class="text-lg font-bold text-slate-100 leading-tight">{{ char.name }}</h3>
                                            {% if loop.first %}
                                                <span class="text-[8px] bg-indigo-600 text-white px-1.5 py-0.5 rounded-full font-black uppercase tracking-wider">Main</span>
                                            {% endif %}
                                        </div>
                                        <p class="text-sm text-indigo-400 font-semibold mb-0.5">{{ char.class }}</p>
                                        <p class="text-[9px] text-slate-600 uppercase tracking-widest">{{ char.realm }}</p>
                                    </div>
                                    
                                    <div class="text-right flex-shrink-0">
                                        <p class="text-[9px] text-slate-600 font-bold uppercase tracking-wider">iLvl</p>
                                        <p class="text-3xl font-black text-white font-mono leading-none">{{ char.ilvl }}</p>
                                    </div>
                                </div>
                                
                                <div class="mt-4 pt-3 border-t border-slate-800/50 flex justify-between items-center">
                                    <a href="{{ char.rio_url }}" target="_blank" class="text-xs text-orange-400 hover:text-orange-300 transition-colors flex items-center gap-1.5 font-medium">
                                        Raider.io <span class="text-[10px]">↗</span>
                                    </a>
                                    
                                    <a href="/delete/{{ user.uid }}/{{ loop.index0 }}" 
                                       onclick="return confirm('Charakter {{ char.name }} wirklich löschen?')" 
                                       class="delete-btn opacity-0 transition-opacity text-slate-700 hover:text-red-500 p-1"
                                       title="Löschen">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </a>
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <div class="text-center py-6 glass rounded-xl border-dashed">
                                <p class="text-slate-600 italic text-sm">Keine Charaktere synchronisiert.</p>
                                <p class="text-[10px] text-slate-700 font-mono mt-1">Nutze /sync_classes im Discord</p>
                            </div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}

            </div>
        </main>

        <footer class="text-center mt-16 text-slate-700 text-[10px] font-mono">
            Gilden Dashboard v2.0 | Sorted by Rank | Confirmed Löschen
        </footer>
    </body>
    </html>
    """
    return await render_template_string(html_template, members_list=enhanced_list, stats=stats)

@app.route('/delete/<uid>/<int:char_idx>')
async def delete_char(uid, char_idx):
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if uid in data and "chars" in data[uid]:
                # Charakter an Position char_idx entfernen
                data[uid]["chars"].pop(char_idx)
                
                # Wenn Liste leer ist, ganzen User löschen
                if not data[uid]["chars"]:
                    del data[uid]
                
                # Speichern
                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                    
        except Exception as e:
            print(f"Fehler beim Löschen: {e}")

    return redirect(url_for('index'))

async def run_web(bot=None):
    global bot_instance
    bot_instance = bot
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)