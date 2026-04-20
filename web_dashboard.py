import os
import json
from quart import Quart, render_template_string

app = Quart(__name__)
DB_FILE = "/app/data/mitglieder_db.json"

CLASS_COLORS = {
    "Death Knight": "#C41E3A", "Demon Hunter": "#A330C9", "Druid": "#FF7C0A",
    "Evoker": "#33937F", "Hunter": "#AAD372", "Mage": "#3FC7EB",
    "Monk": "#00FF98", "Paladin": "#F48CBA", "Priest": "#FFFFFF",
    "Rogue": "#FFF468", "Shaman": "#0070DD", "Warlock": "#8788EE",
    "Warrior": "#C69B6D", "Unbekannt": "#A3A3A3"
}

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

@app.route("/")
async def index():
    db = load_db()
    
    html_template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gilden Dashboard</title>
        <style>
            :root { --bg: #0b0c10; --card-bg: #1f2833; --text: #c5c6c7; --bright: #66fcf1; }
            body { font-family: 'Inter', sans-serif; background-color: var(--bg); color: var(--text); margin: 0; padding: 20px; }
            .header { text-align: center; padding: 40px 0; }
            h1 { color: white; font-size: 2.5em; margin: 0; text-transform: uppercase; letter-spacing: 3px; }
            
            .grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); 
                gap: 20px; 
                padding: 20px;
            }
            
            .member-card {
                background: var(--card-bg);
                border-radius: 12px;
                padding: 20px;
                border-left: 5px solid #444;
                transition: transform 0.2s, box-shadow 0.2s;
                position: relative;
            }
            
            .member-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.4);
            }

            .main-char { font-size: 1.4em; font-weight: bold; color: white; display: block; margin-bottom: 5px; }
            .class-name { font-size: 0.9em; font-weight: bold; text-transform: uppercase; margin-bottom: 15px; display: block; }
            
            .twink-list { 
                margin-top: 15px; 
                padding-top: 10px; 
                border-top: 1px solid #333; 
                font-size: 0.85em;
            }
            .twink-item { color: #888; display: block; padding: 2px 0; }
            
            .realm-tag { position: absolute; top: 15px; right: 15px; font-size: 0.7em; background: #000; padding: 3px 8px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛡️ Gilden-Besetzung</h1>
            <p>Live-Übersicht der aktiven Charaktere</p>
        </div>
        
        <div class="grid">
            {% for uid, data in db.items() %}
                {% if data.chars %}
                <div class="member-card" style="border-left-color: {{ colors.get(data.chars[0].class, '#444') }}">
                    <span class="realm-tag">{{ data.chars[0].realm }}</span>
                    <span class="main-char">👑 {{ data.chars[0].name }}</span>
                    <span class="class-name" style="color: {{ colors.get(data.chars[0].class, '#fff') }}">
                        {{ data.chars[0].class }}
                    </span>
                    
                    {% if data.chars|length > 1 %}
                    <div class="twink-list">
                        {% for twink in data.chars[1:] %}
                            <span class="twink-item">🔹 {{ twink.name }} ({{ twink.class }})</span>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>
                {% endif %}
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return await render_template_string(html_template, db=db, colors=CLASS_COLORS)

async def run_web():
    import os, asyncio
    port = int(os.getenv("PORT", 5000))
    await app.run_task(host="0.0.0.0", port=port)
