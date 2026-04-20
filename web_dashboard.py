import os
import json
from quart import Quart, render_template

app = Quart(__name__)

# Pfad-Logik für Railway oder Lokal
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"

@app.route('/')
async def index():
    members_data = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                members_data = json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden der DB: {e}")

    # Wir berechnen kurz die Stats für die Header-Cards
    char_count = sum(len(u.get('chars', [])) for u in members_data.values())
    
    stats = {
        "total_members": len(members_data),
        "total_chars": char_count,
        "status": "Online"
    }

    # 'members_data' wird als 'members' ans HTML übergeben
    return await render_template('index.html', members=members_data, stats=stats)

def run_web():
    # Diese Funktion wird von deiner Gildenverwaltung.py aufgerufen
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    # Da Quart asynchron ist, nutzen wir Hypercorn zum Servieren
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))