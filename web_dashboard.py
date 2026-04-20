from flask import Flask, render_template
import json
import os

app = Flask(__name__)

# Pfad zu deiner Datenbank aus dem 'data' Ordner
DB_PATH = os.path.join("data", "mitglieder_db.json")

def load_member_data():
    """Lädt die Mitgliederdaten aus der JSON-Datei."""
    if not os.path.exists(DB_PATH):
        return {}
    
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Falls deine JSON-Struktur ein Dictionary mit 'members' ist:
            return data.get("members", data) 
    except Exception as e:
        print(f"Fehler beim Laden der JSON: {e}")
        return {}

@app.route('/')
def index():
    members = load_member_data()
    
    # Statistiken berechnen
    stats = {
        "total": len(members),
        "active": sum(1 for m in members.values() if m.get("status") == "Aktiv"),
        "status": "Online"  # Da das Script läuft, ist das Dashboard online
    }
    
    return render_template('index.html', members=members, stats=stats)

if __name__ == '__main__':
    # Starte den Flask-Server auf Port 5000
    app.run(debug=True, port=5000)