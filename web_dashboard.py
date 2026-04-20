import os
import json
import aiohttp
from quart import Quart, render_template_string, redirect, url_for, request
from quart_discord import DiscordOAuth2Session, requires_authorization

app = Quart(__name__)

# Fix für Railway (erlaubt OAuth2 über interne Verbindungen)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Railway Variablen
app.secret_key = os.getenv("SECRET_KEY", "super-geheim")
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")

discord_auth = DiscordOAuth2Session(app)
DB_FILE = "/app/data/mitglieder_db.json"
MY_ID = "1159119755253383188" # Deine ID als Haupt-Admin

CLASS_COLORS = {
    "Death Knight": "#C41E3A", "Demon Hunter": "#A330C9", "Druid": "#FF7C0A",
    "Evoker": "#33937F", "Hunter": "#AAD372", "Mage": "#3FC7EB",
    "Monk": "#00FF98", "Paladin": "#F48CBA", "Priest": "#FFFFFF",
    "Rogue": "#FFF468", "Shaman": "#0070DD", "Warlock": "#8788EE",
    "Warrior": "#C69B6D", "Unbekannt": "#A3A3A3"
}

async def get_rio_data(name, realm):
    """Fragt Charakterdaten bei Raider.io ab"""
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            return None
    return None

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_db(data):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/login")
async def login():
    return await discord_auth.create_session()

@app.route("/callback")
async def callback():
    try:
        await discord_auth.callback()
    except Exception as e:
        print(f"Callback Fehler: {e}")
    return redirect(url_for("index"))

@app.route("/")
async def index():
    is_logged_in = await discord_auth.authorized
    user = None
    is_admin = False
    
    if is_logged_in:
        try:
            user = await discord_auth.fetch_user()
            if str(user.id) == MY_ID:
                is_admin = True
        except:
            is_logged_in = False

    db = load_db()
    return await render_template_string(HTML_TEMPLATE, db=db, colors=CLASS_COLORS, user=user, is_logged_in=is_logged_in, is_admin=is_admin)

@app.route("/add", methods=["POST"])
@requires_authorization
async def add_char():
    user = await discord_auth.fetch_user()
    if str(user.id) != MY_ID:
        return "Keine Berechtigung", 403

    form = await request.form
    name = form.get("name").strip()
    realm = form.get("realm").strip() or "Blackhand"
    
    # Raider.io API Abfrage
    rio = await get_rio_data(name, realm)
    
    db = load_db()
    uid = str(user.id)
    if uid not in db: db[uid] = {"chars": []}
    
    # Daten zusammenbauen
    new_char = {
        "name": rio["name"] if rio else name.capitalize(),
        "class": rio["class"] if rio else "Unbekannt",
        "realm": rio["realm"] if rio else realm.capitalize(),
        "ilvl": rio["gear"]["item_level_equipped"] if rio else "??",
        "rio_url": rio["profile_url"] if rio else "#"
    }
    
    db[uid]["chars"].append(new_char)
    save_db(db)
    return redirect(url_for("index"))

@app.route("/delete/<uid>/<int:char_index>")
@requires_authorization
async def delete_char(uid, char_index):
    user = await discord_auth.fetch_user()
    if str(user.id) != MY_ID:
        return "Keine Berechtigung", 403

    db = load_db()
    if uid in db and 0 <= char_index < len(db[uid]["chars"]):
        db[uid]["chars"].pop(char_index)
        if not db[uid]["chars"]:
            del db[uid]
        save_db(db)
    return redirect(url_for("index"))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gilden-Verwaltung</title>
    <style>
        :root { --bg: #0f1014; --card: #1a1c23; --primary: #5865F2; --success: #23a559; --danger: #da373c; }
        body { font-family: 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: #eee; margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: auto; }
        
        .header { display: flex; justify-content: space-between; align-items: center; background: var(--card); padding: 20px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #2e3035; }
        h1 { margin: 0; font-size: 1.5rem; display: flex; align-items: center; gap: 10px; }
        
        .btn { padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; cursor: pointer; border: none; font-size: 0.9rem; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.8; }
        .btn-blue { background: var(--primary); color: white; }
        .btn-green { background: var(--success); color: white; }
        .btn-del { background: var(--danger); color: white; padding: 4px 8px; font-size: 0.75rem; }

        .admin-section { background: var(--card); padding: 20px; border-radius: 12px; margin-bottom: 30px; border: 1px solid #333; }
        .admin-section h3 { margin-top: 0; font-size: 1rem; color: #aaa; }
        form { display: flex; gap: 10px; flex-wrap: wrap; }
        input { background: #2a2d37; border: 1px solid #444; color: white; padding: 10px; border-radius: 6px; flex: 1; min-width: 150px; }

        .char-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; }
        .char-card { 
            background: var(--card); padding: 18px; border-radius: 10px; 
            border-left: 5px solid #444; position: relative;
            transition: transform 0.2s; border: 1px solid #2e3035;
        }
        .char-card:hover { transform: translateY(-3px); border-color: #444; }
        
        .char-info { text-decoration: none; color: inherit; display: block; }
        .name { display: block; font-size: 1.2rem; font-weight: bold; margin-bottom: 4px; }
        .class-name { font-size: 0.85rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
        .realm { font-size: 0.75rem; color: #888; margin-top: 5px; }
        .ilvl-badge { position: absolute; top: 18px; right: 18px; background: #2a2d37; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; color: #66fcf1; }
        
        .actions { margin-top: 15px; display: flex; justify-content: flex-end; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ Gilden-Verwaltung</h1>
            {% if not is_logged_in %}
                <a href="/login" class="btn btn-blue">Mit Discord einloggen</a>
            {% else %}
                <div style="display:flex; align-items:center; gap:15px;">
                    <span style="font-size: 0.9rem;">Eingeloggt als <strong>{{ user.name }}</strong></span>
                    <a href="/login" style="font-size: 0.7rem; color: #666;">Wechseln</a>
                </div>
            {% endif %}
        </div>

        {% if is_admin %}
        <div class="admin-section">
            <h3>✨ Charakter hinzufügen (Automatisch via Raider.io)</h3>
            <form action="/add" method="post">
                <input type="text" name="name" placeholder="Charakter Name" required>
                <input type="text" name="realm" placeholder="Realm (Standard: Blackhand)">
                <button type="submit" class="btn btn-green">Hinzufügen</button>
            </form>
        </div>
        {% endif %}

        <div class="char-grid">
            {% for uid, data in db.items() %}
                {% set outer_loop = loop %}
                {% for char in data.chars %}
                <div class="char-card" style="border-left-color: {{ colors.get(char.class, '#444') }}">
                    <a href="{{ char.rio_url }}" target="_blank" class="char-info">
                        <span class="ilvl-badge">{{ char.ilvl }} iLvl</span>
                        <span class="name">{{ char.name }}</span>
                        <span class="class-name" style="color: {{ colors.get(char.class, '#fff') }}">{{ char.class }}</span>
                        <div class="realm">{{ char.realm }}</div>
                    </a>
                    
                    {% if is_admin %}
                    <div class="actions">
                        <a href="/delete/{{uid}}/{{loop.index0}}" class="btn btn-del" onclick="return confirm('Wirklich löschen?')">Löschen</a>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

async def run_web():
    import asyncio
    port = int(os.getenv("PORT", 5000))
    await app.run_task(host="0.0.0.0", port=port)
