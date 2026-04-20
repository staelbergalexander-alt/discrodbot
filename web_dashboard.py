import os
import json
import aiohttp
import re
from quart import Quart, render_template_string, redirect, url_for, request
from quart_discord import DiscordOAuth2Session, requires_authorization

app = Quart(__name__)

# WICHTIG: Erlaubt OAuth2 über Railway's interne HTTP-Verbindung
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Railway Umgebungsvariablen
app.secret_key = os.getenv("SECRET_KEY", "ein-sehr-geheimer-schluessel")
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")

discord_auth = DiscordOAuth2Session(app)
DB_FILE = "/app/data/mitglieder_db.json"
MY_ID = "1159119755253383188" # Deine Discord-ID für Admin-Rechte

CLASS_COLORS = {
    "Death Knight": "#C41E3A", "Demon Hunter": "#A330C9", "Druid": "#FF7C0A",
    "Evoker": "#33937F", "Hunter": "#AAD372", "Mage": "#3FC7EB",
    "Monk": "#00FF98", "Paladin": "#F48CBA", "Priest": "#FFFFFF",
    "Rogue": "#FFF468", "Shaman": "#0070DD", "Warlock": "#8788EE",
    "Warrior": "#C69B6D", "Unbekannt": "#A3A3A3"
}

# --- HELPER FUNKTIONEN ---

def parse_rio_link(link):
    """Extrahiert Realm und Name aus einem Raider.io Link"""
    match = re.search(r"characters/eu/([^/]+)/([^/]+)", link)
    if match:
        return match.group(1).lower(), match.group(2).lower()
    return None, None

async def get_rio_data(name, realm):
    """Holt iLvl und Klasse von der Raider.io API"""
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            print(f"Raider.io API Fehler: {e}")
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

# --- ROUTES ---

@app.route("/login")
async def login():
    return await discord_auth.create_session()

@app.route("/callback")
async def callback():
    try:
        await discord_auth.callback()
    except Exception as e:
        print(f"Login Fehler: {e}")
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
        return "Nur der Admin darf Charaktere hinzufügen.", 403

    form = await request.form
    link = form.get("rio_link", "").strip()
    
    realm, name = parse_rio_link(link)
    if not name or not realm:
        return "Ungültiger Link! Bitte kopiere einen EU-Raider.io Link.", 400

    rio_info = await get_rio_data(name, realm)
    
    db = load_db()
    uid = str(user.id)
    if uid not in db:
        db[uid] = {"discord_name": user.name, "chars": []}
    
    new_char = {
        "name": rio_info["name"] if rio_info else name.capitalize(),
        "class": rio_info["class"] if rio_info else "Unbekannt",
        "realm": rio_info["realm"] if rio_info else realm.capitalize(),
        "ilvl": rio_info["gear"]["item_level_equipped"] if rio_info else "??",
        "rio_url": link,
        "added_by": user.name
    }
    
    db[uid]["chars"].append(new_char)
    save_db(db)
    return redirect(url_for("index"))

@app.route("/delete/<uid>/<int:index>")
@requires_authorization
async def delete_char(uid, index):
    user = await discord_auth.fetch_user()
    if str(user.id) != MY_ID:
        return "Keine Berechtigung", 403

    db = load_db()
    if uid in db and 0 <= index < len(db[uid]["chars"]):
        db[uid]["chars"].pop(index)
        if not db[uid]["chars"]:
            del db[uid]
        save_db(db)
    return redirect(url_for("index"))

# --- HTML DESIGN ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gilden Dashboard</title>
    <style>
        :root { --bg: #0b0c10; --card: #1f2833; --cyan: #66fcf1; --text: #eee; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: auto; }
        
        header { display: flex; justify-content: space-between; align-items: center; padding: 20px; background: var(--card); border-radius: 12px; margin-bottom: 30px; border-bottom: 3px solid var(--cyan); }
        .btn { padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; display: inline-block; }
        .btn-discord { background: #5865F2; color: white; }
        .btn-add { background: var(--cyan); color: #0b0c10; width: 100%; max-width: 200px; }
        
        .admin-panel { background: var(--card); padding: 25px; border-radius: 12px; margin-bottom: 40px; border: 1px solid #333; }
        input { background: #0b0c10; border: 1px solid var(--cyan); color: white; padding: 12px; border-radius: 6px; width: 100%; max-width: 500px; margin-bottom: 10px; }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
        .card { background: var(--card); border-radius: 12px; padding: 20px; position: relative; border: 1px solid #333; transition: 0.3s; }
        .card:hover { border-color: var(--cyan); transform: translateY(-5px); }
        
        .ilvl { position: absolute; top: 15px; right: 15px; color: var(--cyan); font-weight: bold; font-size: 1.1rem; }
        .class-label { font-weight: bold; text-transform: uppercase; font-size: 0.8rem; margin-bottom: 5px; display: block; }
        
        .owner-box { font-size: 0.8rem; color: #888; margin-top: 15px; border-top: 1px solid #333; padding-top: 10px; }
        .discord-id { font-family: monospace; color: var(--cyan); background: rgba(102, 252, 241, 0.1); padding: 2px 5px; border-radius: 4px; font-size: 0.75rem; display: inline-block; margin-top: 5px; }
        
        .del-link { color: #ff4d4d; font-size: 0.75rem; text-decoration: none; float: right; font-weight: bold; }
        .del-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🛡️ Gilden Dashboard</h1>
            {% if not is_logged_in %}
                <a href="/login" class="btn btn-discord">Login mit Discord</a>
            {% else %}
                <span>Eingeloggt: <strong>{{ user.name }}</strong></span>
            {% endif %}
        </header>

        {% if is_admin %}
        <section class="admin-panel">
            <h3>➕ Charakter hinzufügen (Raider.io Link)</h3>
            <form action="/add" method="post">
                <input type="text" name="rio_link" placeholder="https://raider.io/characters/eu/realm/character" required>
                <button type="submit" class="btn btn-add">Hinzufügen</button>
            </form>
        </section>
        {% endif %}

        <div class="grid">
            {% for uid, data in db.items() %}
                {% set discord_name = data.discord_name %}
                {% for char in data.chars %}
                <div class="card" style="border-top: 4px solid {{ colors.get(char.class, '#444') }}">
                    <div class="ilvl">{{ char.ilvl }}</div>
                    <span class="class-label" style="color: {{ colors.get(char.class, '#fff') }}">{{ char.class }}</span>
                    <strong style="font-size: 1.4rem;">{{ char.name }}</strong><br>
                    <small>{{ char.realm }}</small>
                    
                    <div class="owner-box">
                        👤 <strong>Besitzer:</strong> {{ discord_name }}<br>
                        <span class="discord-id">ID: {{ uid }}</span>
                        
                        {% if is_admin %}
                            <a href="/delete/{{uid}}/{{loop.index0}}" class="del-link" onclick="return confirm('Charakter wirklich entfernen?')">❌ Löschen</a>
                        {% endif %}
                    </div>
                    
                    <a href="{{ char.rio_url }}" target="_blank" style="display:block; margin-top:12px; font-size: 0.8rem; color: var(--cyan); text-decoration: none;">Raider.io Profil ↗</a>
                </div>
                {% endfor %}
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

async def run_web():
    port = int(os.getenv("PORT", 5000))
    await app.run_task(host="0.0.0.0", port=port)
