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
        role_info = {"name": "Gast", "color": "slate-500", "priority": 4}
        joined_date = None
        
        if guild:
            member = guild.get_member(int(uid))
            if member:
                # Beitrittsdatum formatieren (TT.MM.JJJJ)
                if member.joined_at:
                    joined_date = member.joined_at.strftime("%d.%m.%Y")
                
                role_ids = [r.id for r in member.roles]
                if OFFIZIER_ROLLE_ID in role_ids:
                    role_info = {"name": "Offizier", "color": "red-500", "priority": 1}
                elif MITGLIED_ROLLE_ID in role_ids:
                    role_info = {"name": "Mitglied", "color": "emerald-500", "priority": 2}
                elif BEWERBER_ROLLE_ID in role_ids:
                    role_info = {"name": "Bewerber", "color": "amber-500", "priority": 3}

        enhanced_list.append({
            "uid": uid,
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
        <script src="https://cdn.tailwindcss.com"></script>
        <title>Gilden Dashboard</title>
    </head>
    <body class="bg-[#0f172a] text-slate-200 min-h-screen font-sans">
        <header class="p-8 bg-[#1e293b] border-b border-indigo-500/50 shadow-2xl mb-10 text-center">
            <h1 class="text-4xl font-black text-indigo-400 tracking-tighter italic">🛡️ GILDEN DASHBOARD</h1>
            <div class="flex justify-center gap-4 mt-4">
                <span class="bg-indigo-500/20 text-indigo-300 px-4 py-1 rounded-full text-sm border border-indigo-500/30">👤 Spieler: {{ stats.total_members }}</span>
                <span class="bg-emerald-500/20 text-emerald-300 px-4 py-1 rounded-full text-sm border border-emerald-500/30">⚔️ Charaktere: {{ stats.total_chars }}</span>
            </div>
        </header>

        <div class="container mx-auto px-4 pb-20">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {% for user in members_list %}
                <div class="bg-[#1e293b] rounded-2xl p-6 border border-slate-700 hover:border-indigo-500/50 transition-all shadow-xl relative overflow-hidden">
                    
                    <div class="absolute top-0 right-0 flex flex-col items-end">
                        <div class="px-3 py-1 bg-{{ user.role.color }}/20 border-b border-l border-{{ user.role.color }}/30 rounded-bl-lg">
                            <span class="text-[10px] font-bold text-{{ user.role.color }} uppercase tracking-tighter">{{ user.role.name }}</span>
                        </div>
                        
                        {% if user.role.name == "Bewerber" and user.joined_at %}
                        <div class="mr-2 mt-1">
                            <span class="text-[9px] text-slate-500 font-mono">Seit: {{ user.joined_at }}</span>
                        </div>
                        {% endif %}
                    </div>

                    <div class="mb-4">
                        <h2 class="text-slate-400 text-[10px] font-mono opacity-50">UID: ...{{ user.uid[-6:] }}</h2>
                    </div>

                    <div class="space-y-4">
                        {% for char in user.chars %}
                        <div class="bg-[#0f172a]/50 p-4 rounded-xl border-l-4 border-indigo-500 shadow-inner">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h3 class="text-xl font-bold text-white leading-tight">{{ char.name }}</h3>
                                    <p class="text-sm text-indigo-400 font-medium">{{ char.class }}</p>
                                </div>
                                <div class="bg-indigo-500/10 border border-indigo-500/50 text-indigo-300 px-3 py-1 rounded-lg text-center">
                                    <span class="text-[8px] block text-slate-500 uppercase font-bold">iLvl</span>
                                    <span class="font-mono font-bold">{{ char.ilvl }}</span>
                                </div>
                            </div>
                            <div class="mt-4 pt-3 border-t border-slate-700/50 flex justify-between items-center">
                                <a href="{{ char.rio_url }}" target="_blank" class="text-xs text-orange-400 hover:text-orange-300">🔗 Raider.io</a>
                                <div class="flex gap-2 items-center">
                                    {% if loop.first %}
                                        <span class="text-[9px] bg-indigo-600 text-white px-2 py-0.5 rounded-full font-bold">MAIN</span>
                                    {% endif %}
                                    <a href="/delete/{{ user.uid }}/{{ loop.index0 }}" onclick="return confirm('Löschen?')" class="text-slate-600 hover:text-red-500 transition-colors">🗑️</a>
                                </div>
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