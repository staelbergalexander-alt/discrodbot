import os
import json
from quart import Quart, render_template_string

app = Quart(__name__)

# Pfad zur Datenbank (muss der gleiche sein wie im Bot)
DB_FILE = "/app/data/mitglieder_db.json"

# Mapping für WoW Klassenfarben
CLASS_COLORS = {
    "Death Knight": "#C41E3A",
    "Demon Hunter": "#A330C9",
    "Druid": "#FF7C0A",
    "Evoker": "#33937F",
    "Hunter": "#AAD372",
    "Mage": "#3FC7EB",
    "Monk": "#00FF98",
    "Paladin": "#F48CBA",
    "Priest": "#FFFFFF",
    "Rogue": "#FFF468",
    "Shaman": "#0070DD",
    "Warlock": "#8788EE",
    "Warrior": "#C69B6D",
    "Unbekannt": "#A3A3A3"
}

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
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
            body { 
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
                background-color: #121212; 
                color: #e0e0e0; 
                margin: 0; 
                padding: 20px;
            }
            .container { max-width: 1100px; margin: auto; }
            h1 { 
                text-align: center; 
                color: #fff; 
                margin-bottom: 30px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
            }
            table { 
                width: 100%; 
                border-collapse: collapse; 
                background: #1e1e1e; 
                border-radius: 8px; 
                overflow: hidden;
                box-shadow: 0 10px 20px rgba(0,0,0,0.5);
            }
            th { 
                background-color: #2d2d2d; 
                color: #aaaaaa; 
                text-transform: uppercase; 
                letter-spacing: 1px;
                font-size: 13px;
                padding: 15px;
                text-align: left;
            }
            td { 
                padding: 12px 15px; 
                border-bottom: 1px solid #333;
            }
            tr:hover { background-color: #252525; }
            
            .class-badge {
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
            }
            
            .main-icon { color: #ffcc00; margin-right: 8px; font-size: 1.2em; }
            .twink-space { margin-left: 28px; }
            
            .footer { 
                text-align: center; 
                margin-top: 40px; 
                font-size: 0.8em; 
                color: #666;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Gilden-Besetzung</h1>
            <table>
                <thead>
                    <tr>
                        <th>Charakter</th>
                        <th>Klasse</th>
                        <th>Realm</th>
                    </tr>
                </thead>
                <tbody>
                    {% for uid, data in db.items() %}
                        {% for char in data.chars %}
                        <tr>
                            <td>
                                {% if loop.index0 == 0 %}
                                    <span class="main-icon">👑</span>
                                {% else %}
                                    <span class="twink-space"></span>
                                {% endif %}
                                <strong>{{ char.name }}</strong>
                            </td>
                            <td>
                                <span class="class-badge" style="background-color: {{ colors.get(char.class, '#444') }}; color: white;">
                                    {{ char.class }}
                                </span>
                            </td>
                            <td>{{ char.realm }}</td>
                        </tr>
                        {% endfor %}
                    {% endfor %}
                </tbody>
            </table>
            <div class="footer">Live-Daten aus der Gilden-Datenbank</div>
        </div>
    </body>
    </html>
    """
    return await render_template_string(html_template, db=db, colors=CLASS_COLORS)

async def run_web():
    # Railway nutzt die PORT Umgebungsvariable
    port = int(os.getenv("PORT", 5000))
    
    # FIX: Wir nutzen direkt das Standard-asyncio von Python
    import asyncio
    
    # Wir erstellen eine Task für den Quart-Server
    await app.run_task(host="0.0.0.0", port=port)
