import os
import json
from quart import Quart, render_template

app = Quart(__name__)

# Pfad-Check für Railway vs. Lokal
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"

@app.route('/')
async def index():
    members_data = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                members_data = json.load(f)
        except Exception as e:
            print(f"Fehler: {e}")

    # Wir berechnen Statistiken
    total_chars = 0
    for uid in members_data:
        total_chars += len(members_data[uid].get('chars', []))

    stats = {
        "total_members": len(members_data),
        "total_chars": total_chars,
        "status": "Online"
    }

    # Wir übergeben die Daten an das HTML
    return await render_template('index.html', members=members_data, stats=stats)

def run_web():
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    asyncio.run(serve(app, config))