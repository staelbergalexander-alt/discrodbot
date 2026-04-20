import os
import json
import discord
import asyncio
from quart import Quart, render_template_string, redirect, url_for
from datetime import datetime

app = Quart(__name__)

# Pfade & IDs
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)

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
            print(f"Fehler beim Laden: {e}")

    enhanced_list = []
    total_chars = 0
    guild = bot_instance.get_guild(SERVER_ID) if bot_instance and bot_instance.is_ready() else None

    for uid, user_data in members_data.items():
        role_info = {"name": "Gast", "color": "slate", "priority": 4}
        joined_date = None
        display_name = f"User {uid[-4:]}" # Fallback Name
        
        if guild:
            member = guild.get_member(int(uid))
            if member:
                display_name = member.display_name
                if member.joined_at:
                    joined_date = member.joined_at.strftime("%d.%m.%Y")
                
                role_ids = [r.id for r in member.roles]
                if OFFIZIER_ROLLE_ID in role_ids:
                    role_info = {"name": "Offizier", "color": "red", "priority": 1}
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
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
        <title>Gilden Dashboard</title>
        <style>
            body { font-family: 'Inter', sans-serif; background: radial-gradient(circle at top right, #1e293b, #0f172a); }
            .card-gradient { background: linear-gradient(145deg, #1e293b 0%, #111827 100%); }
        </style>
    </head>
    <body class="text-slate-200 min-h-screen pb-20">
        
        <header class="relative py-12 px-4 mb-12 overflow-hidden">
            <div class="absolute inset-0 bg-indigo-600/10 blur-3xl -z-10"></div>
            <div class="container mx-auto text-center">
                <h1 class="text-5xl font-extrabold tracking-tight text-white mb-4 italic uppercase">
                    🛡️ Gilden<span class="text-indigo-500 underline decoration-indigo-500/30">Dashboard</span>
                </h1>
                <div class="flex justify-center items-center gap-6">
                    <div class="px-6 py-2 bg-slate-800/50 rounded-2xl border border-slate-700 backdrop-blur-sm">
                        <p class="text-xs text-slate-400 uppercase font-bold tracking-widest">Mitglieder</p>
                        <p class="text-2xl font-black text-indigo-400">{{ stats.total_members }}</p>
                    </div>
                    <div class="px-6 py-2 bg-slate-800/50 rounded-2xl border border-slate-700 backdrop-blur-sm">
                        <p class="text-xs text-slate-400 uppercase font-bold tracking-widest">Charaktere</p>
                        <p class="text-2xl font-black text-emerald-400">{{ stats.total_chars }}</p>
                    </div>
                </div>
            </div>
        </header>

        <main class="container mx-auto px-4">
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
                {% for user in members_list %}
                <div class="card-gradient rounded-3xl border border-slate-700/50 shadow-2xl overflow-hidden flex flex-col transition-transform hover:scale-[1.01]">
                    
                    <div class="p-5 border-b border-slate-700/50 flex justify-between items-center bg-slate-800/30">
                        <div>
                            <h2 class="text-xl font-bold text-white tracking-tight">{{ user.name }}</h2>
                            <p class="text-[10px] font-mono text-slate-500 uppercase">ID: ...{{ user.uid[-6:] }}</p>
                        </div>
                        <div class="text-right">
                            <span class="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest bg-{{ user.role.color }}-500/10 border border-{{ user.role.color }}-500/20 text-{{ user.role.color }}-400">
                                {{ user.role.name }}
                            </span>
                            {% if user.joined_at %}
                            <p class="text-[9px] text-slate-500 mt-1 font-medium italic">Seit {{ user.joined_at }}</p>
                            {% endif %}
                        </div>
                    </div>

                    <div class="p-5 space-y-4 flex-grow">
                        {% for char in user.chars %}
                        <div class="group bg-slate-900/50 rounded-2xl p-4 border border-slate-700/30 hover:border-indigo-500/30 transition-all">
                            <div class="flex justify-between items-center">
                                <div>
                                    <div class="flex items-center gap-2">
                                        <h3 class="font-bold text-slate-100">{{ char.name }}</h3>
                                        {% if loop.first %}
                                        <span class="text-[8px] bg-indigo-500 text-white px-1.5 py-0.5 rounded font-black uppercase">Main</span>
                                        {% endif %}
                                    </div>
                                    <p class="text-xs text-indigo-400 font-semibold">{{ char.class }}</p>
                                    <p class="text-[9px] text-slate-500 uppercase tracking-tighter">{{ char.realm }}</p>
                                </div>
                                <div class="text-right">
                                    <p class="text-[8px] text-slate-500 font-bold uppercase">Item Level</p>
                                    <p class="text-xl font-black text-white font-mono">{{ char.ilvl }}</p>
                                </div>
                            </div>
                            
                            <div class="mt-3 pt-3 border-t border-slate-800 flex justify-between items-center">
                                <a href="{{ char.rio_url }}" target="_blank" class="text-[10px] font-bold text-orange-400 hover:text-orange-300 transition-colors flex items-center gap-1">
                                    Raider.io ↗
                                </a>
                                <a href="/delete/{{ user.uid }}/{{ loop.index0 }}" 
                                   onclick="return confirm('Charakter {{ char.name }} entfernen?')" 
                                   class="opacity-0 group-hover:opacity-100 transition-opacity text-slate-600 hover:text-red-500">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </a>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </main>
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
                data[uid]["chars"].pop(char_idx)
                if not data[uid]["chars"]: del data[uid]
                with open(DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e: print(f"Löschfehler: {e}")
    return redirect(url_for('index'))

async def run_web(bot=None):
    global bot_instance
    bot_instance = bot
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)