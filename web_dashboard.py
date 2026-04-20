import os
import json
import aiohttp
import re
from quart import Quart, render_template_string, redirect, url_for, request
from quart_discord import DiscordOAuth2Session, requires_authorization

app = Quart(__name__)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app.secret_key = os.getenv("SECRET_KEY", "geheim123")
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")

discord_auth = DiscordOAuth2Session(app)
DB_FILE = "/app/data/mitglieder_db.json"
MY_ID = "1159119755253383188"

CLASS_COLORS = {
    "Death Knight": "#C41E3A", "Demon Hunter": "#A330C9", "Druid": "#FF7C0A",
    "Evoker": "#33937F", "Hunter": "#AAD372", "Mage": "#3FC7EB",
    "Monk": "#00FF98", "Paladin": "#F48CBA", "Priest": "#FFFFFF",
    "Rogue": "#FFF468", "Shaman": "#0070DD", "Warlock": "#8788EE",
    "Warrior": "#C69B6D", "Unbekannt": "#A3A3A3"
}

def parse_rio_link(link):
    match = re.search(r"characters/eu/([^/]+)/([^/]+)", link)
    if match: return match.group(1).lower(), match.group(2).lower()
    return None, None

async def get_rio_data(name, realm):
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.json()
        except: return None
    return None

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_db(data):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

@app.route("/login")
async def login(): return await discord_auth.create_session()

@app.route("/callback")
async def callback():
    await discord_auth.callback()
    return redirect(url_for("index"))

@app.route("/")
async def index():
    is_logged_in = await discord_auth.authorized
    user = None
    is_admin = False
    if is_logged_in:
        user = await discord_auth.fetch_user()
        if str(user.id) == MY_ID: is_admin = True
    db = load_db()
    return await render_template_string(HTML_TEMPLATE, db=db, colors=CLASS_COLORS, user=user, is_logged_in=is_logged_in, is_admin=is_admin)

@app.route("/add", methods=["POST"])
@requires_authorization
async def add_char():
    admin_user = await discord_auth.fetch_user()
    if str(admin_user.id) != MY_ID: return "Rechte fehlen", 403
    form = await request.form
    link = form.get("rio_link", "").strip()
    target_uid = form.get("discord_id", "").strip() or str(admin_user.id)
    realm, name = parse_rio_link(link)
    if not name: return "Link ungültig", 400
    rio = await get_rio_data(name, realm)
    db = load_db()
    if target_uid not in db: db[target_uid] = {"discord_name": f"User_{target_uid[:5]}", "chars": []}
    db[target_uid]["chars"].append({
        "name": rio["name"] if rio else name.capitalize(),
        "class": rio["class"] if rio else "Unbekannt",
        "realm": rio["realm"] if rio else realm.capitalize(),
        "ilvl": rio["gear"]["item_level_equipped"] if rio else "??",
        "rio_url": link
    })
    save_db(db)
    return redirect(url_for("index"))

@app.route("/delete/<uid>/<int:index>")
@requires_authorization
async def delete_char(uid, index):
    user = await discord_auth.fetch_user()
    if str(user.id) == MY_ID:
        db = load_db()
        if uid in db and 0 <= index < len(db[uid]["chars"]):
            db[uid]["chars"].pop(index)
            if not db[uid]["chars"]: del db[uid]
            save_db(db)
    return redirect(url_for("index"))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Gilden Dashboard</title>
    <style>
        :root { --bg: #0b0c10; --card: #1f2833; --cyan: #66fcf1; --text: #eee; }
        body { font-family: sans-serif; background: var(--bg); color: var(--text); padding: 20px; }
        .container { max-width: 1100px; margin: auto; }
        .admin-panel { background: var(--card); padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid var(--cyan); }
        
        /* Container für einen Spieler (Main + Twinks) */
        .player-group { 
            background: rgba(255,255,255,0.02); 
            border-radius: 15px; 
            padding: 15px; 
            margin-bottom: 30px; 
            border: 1px solid #333;
        }
        .player-header { border-bottom: 1px solid #444; padding-bottom: 10px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }
        .discord-id { font-family: monospace; color: var(--cyan); font-size: 0.8rem; }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; }
        
        /* Main Charakter Karte */
        .card.main { border-left: 6px solid; transform: scale(1.02); background: #2a343f; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        /* Twink Karte */
        .card.twink { border-left: 3px solid; opacity: 0.9; font-size: 0.9rem; }
        
        .card { background: var(--card); padding: 15px; border-radius: 10px; position: relative; }
        .ilvl { position: absolute; top: 10px; right: 10px; color: var(--cyan); font-weight: bold; }
        .label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; font-weight: bold; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.3); }
    </style>
</head>
<body>
    <div class="container">
        <header style="display:flex; justify-content: space-between; align-items: center; margin-bottom:30px;">
            <h1>🛡️ Gilden Dashboard</h1>
            {% if is_logged_in %}<span>Hallo <strong>{{ user.name }}</strong></span>{% else %}<a href="/login" style="color:var(--cyan);">Login</a>{% endif %}
        </header>

        {% if is_admin %}
        <div class="admin-panel">
            <form action="/add" method="post">
                <input type="text" name="rio_link" placeholder="Raider.io Link" required style="width:40%; padding:10px; border-radius:5px; border:none;">
                <input type="text" name="discord_id" placeholder="Discord User ID" style="width:30%; padding:10px; border-radius:5px; border:none;">
                <button type="submit" style="padding:10px 20px; background:var(--cyan); border:none; border-radius:5px; font-weight:bold;">Hinzufügen</button>
            </form>
        </div>
        {% endif %}

        {% for uid, data in db.items() %}
        <div class="player-group">
            <div class="player-header">
                <span>👤 Spieler: <strong>{{ data.discord_name or 'Unbekannt' }}</strong></span>
                <span class="discord-id">ID: {{ uid }}</span>
            </div>
            
            <div class="grid">
                {% for char in data.chars %}
                    {% set is_main = loop.first %}
                    <div class="card {{ 'main' if is_main else 'twink' }}" style="border-left-color: {{ colors.get(char.class, '#444') }}">
                        <div class="ilvl">{{ char.ilvl }}</div>
                        <span class="label" style="color: {{ colors.get(char.class, '#fff') }}">
                            {{ '⭐ MAIN' if is_main else '⚓ TWINK' }}
                        </span>
                        <div style="margin-top:10px;">
                            <strong style="font-size: {{ '1.3rem' if is_main else '1.1rem' }};">{{ char.name }}</strong><br>
                            <small>{{ char.class }} - {{ char.realm }}</small>
                        </div>
                        <div style="margin-top:10px; border-top: 1px solid rgba(255,255,255,0.1); padding-top:10px;">
                            <a href="{{ char.rio_url }}" target="_blank" style="color:var(--cyan); text-decoration:none; font-size:0.75rem;">Raider.io ↗</a>
                            {% if is_admin %}
                                <a href="/delete/{{uid}}/{{loop.index0}}" style="color:#ff4d4d; float:right; text-decoration:none; font-size:0.75rem;" onclick="return confirm('Löschen?')">Entfernen</a>
                            {% endif %}
                        </div>
                    </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

async def run_web():
    port = int(os.getenv("PORT", 5000))
    await app.run_task(host="0.0.0.0", port=port)
