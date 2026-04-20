import os
import json
from quart import Quart, render_template_string, redirect, url_for

app = Quart(__name__)

# Pfad zur Datenbank (angepasst an Railway und Lokal)
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"

@app.route('/')
async def index():
    members_data = {}
    
    # 1. Daten aus der JSON laden
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    members_data = json.loads(content)
        except Exception as e:
            print(f"Fehler beim Laden der JSON: {e}")

    # 2. Statistiken berechnen
    total_chars = 0
    if isinstance(members_data, dict):
        for user in members_data.values():
            if isinstance(user, dict) and "chars" in user:
                total_chars += len(user["chars"])
    
    stats = {
        "total_members": len(members_data),
        "total_chars": total_chars
    }

    # 3. Dein HTML-Design mit eingebautem Lösch-Link
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
                <span class="bg-indigo-500/20 text-indigo-300 px-4 py-1 rounded-full text-sm border border-indigo-500/30">
                    👤 Spieler: {{ stats.total_members }}
                </span>
                <span class="bg-emerald-500/20 text-emerald-300 px-4 py-1 rounded-full text-sm border border-emerald-500/30">
                    ⚔️ Charaktere: {{ stats.total_chars }}
                </span>
            </div>
        </header>

        <div class="container mx-auto px-4 pb-20">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                
                {% for uid, user_data in members.items() %}
                <div class="bg-[#1e293b] rounded-2xl p-6 border border-slate-700 hover:border-indigo-500/50 transition-all shadow-xl">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-slate-400 text-xs font-mono">ID: ...{{ uid[-6:] if uid|length > 6 else uid }}</h2>
                        <span class="text-[10px] bg-slate-700 px-2 py-0.5 rounded text-slate-400 uppercase tracking-widest">User Card</span>
                    </div>

                    <div class="space-y-4">
                        {% if user_data.chars %}
                            {% for char in user_data.chars %}
                            <div class="bg-[#0f172a]/50 p-4 rounded-xl border-l-4 border-indigo-500 shadow-inner">
                                <div class="flex justify-between items-start">
                                    <div>
                                        <h3 class="text-xl font-bold text-white leading-tight">{{ char.name }}</h3>
                                        <p class="text-sm text-indigo-400 font-medium">{{ char.class }}</p>
                                        <p class="text-[10px] text-slate-500 uppercase">{{ char.realm }}</p>
                                    </div>
                                    <div class="bg-indigo-500/10 border border-indigo-500/50 text-indigo-300 px-3 py-1 rounded-lg text-center">
                                        <span class="text-xs block text-slate-500 uppercase font-bold text-[8px]">iLvl</span>
                                        <span class="font-mono font-bold">{{ char.ilvl }}</span>
                                    </div>
                                </div>
                                
                                <div class="mt-4 pt-3 border-t border-slate-700/50 flex justify-between items-center">
                                    <a href="{{ char.rio_url }}" target="_blank" class="text-xs text-orange-400 hover:text-orange-300 flex items-center gap-1">
                                        🔗 Raider.io
                                    </a>
                                    
                                    <div class="flex gap-2 items-center">
                                        {% if loop.first %}
                                            <span class="text-[9px] bg-indigo-600 text-white px-2 py-0.5 rounded-full font-bold">MAIN</span>
                                        {% else %}
                                            <span class="text-[9px] bg-slate-700 text-slate-400 px-2 py-0.5 rounded-full">TWINK</span>
                                        {% endif %}
                                        
                                        <a href="/delete/{{ uid }}/{{ loop.index0 }}" 
                                           onclick="return confirm('Soll {{ char.name }} wirklich gelöscht werden?')"
                                           class="text-[10px] text-red-500 hover:text-white hover:bg-red-600 px-2 py-0.5 rounded border border-red-500/30 transition-all">
                                           🗑️
                                        </a>
                                    </div>
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <p class="text-slate-500 italic text-sm text-center">Keine Charaktere gefunden.</p>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}

            </div>
        </div>
    </body>
    </html>
    """
    return await render_template_string(html_template, members=members_data, stats=stats)

# --- NEU: ROUTE ZUM LÖSCHEN ---
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

# Start-Funktion für Gildenverwaltung.py
async def run_web():
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    
    config = Config()
    # Port 5000 oder Railway Port
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)

if __name__ == "__main__":
    app.run(debug=True, port=5000)