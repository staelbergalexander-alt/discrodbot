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
    # Namen des Users in der DB aktualisieren, wenn er sich einloggt
    user = await discord_auth.fetch_user()
    db = load_db()
    uid = str(user.id)
    if uid in db:
        db[uid]["discord_name"] = user.name
        save_db(db)
    return redirect(url_for("index"))

@app.route("/")
async def index():
    is_logged_in = await discord_auth.authorized
    user = None
    is_admin = False
    if is_logged_in:
        try:
            user = await discord_auth.fetch_user()
            if str(user.id) == MY_ID: is_admin = True
        except: is_logged_in = False
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
    
    if target_uid not in db: 
        db[target_uid] = {"discord_name": f"User_{target_uid[-4:]}", "chars": []}
    
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
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); padding: 20px; margin: 0; }
        .container { max-width: 1100px; margin: auto; }
        header { display: flex; justify-content: space-between; align-items: center; padding: 20px; background: var(--card); border-radius: 12px; margin-bottom: 30px; border-bottom: 3px solid var(--cyan); }
        .admin-panel { background: var(--card); padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #333; }
        input { background: #0b0c10; border: 1px solid var(--cyan); color: white; padding: 10px; border-radius: 5px; margin-right: 5px; }
        .player-group { background: rgba(255,255,255,0.03); border-radius: 15px; padding: 20px; margin-bottom: 30px; border: 1px solid #222; }
        .player-header { border-bottom: 1px solid #444; padding-bottom: 10px; margin-bottom: 15px; display: flex; justify-content: space-between; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; }
        .card { background: var(--card); padding: 15px; border-radius: 10px; position: relative; border-left: 5px solid #444; }
        .card.main { background: #262e3b; border-width: 8px; transform: scale(1.02); }
        .ilvl { position: absolute; top: 10px; right: 10px; color: var(--cyan); font-weight: bold; }
        .label { font-size: 0.7rem; font-weight: bold; padding: 2px 5px; border-radius: 3px; background: rgba(0,0,0,0.4); }
        .btn-rio { color: var(--cyan); text-decoration: none; font-size: 0.8rem; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🛡️ Gilden Dashboard</h1>
            {% if is_logged_in %}<span>Hallo <strong>{{ user.name }}</strong></span>{% else %}<a href="/login" style="color:var(--cyan);">Login</a>{% endif %}
        </header>

        {% if is_admin %}
        <div class="admin-panel">
            <form action="/add" method="post">
                <input type="text" name="rio_link" placeholder="Raider.io Link" required style="width:40%;">
                <input type="text" name="discord_id" placeholder="Discord ID des Spielers" style="width:30%;">
                <button type="submit" style="padding:10px; background:var(--cyan); border:none; border-radius:5px; font-weight:bold; cursor:pointer;">Hinzufügen</button>
            </form>
        </div>
        {% endif %}

        {% for uid, data in db.items() %}
        <div class="player-group">
            <div class="player-header">
                <span>👤 Spieler: <strong>{{ data.discord_name if data.discord_name else 'Spieler ' + uid[-4:] }}</strong></span>
                <span style="font-family: monospace; color:#666;">ID: {{ uid }}</span>
            </div>
            <div class="grid">
                {% for char in data.chars %}
                {% set is_main = loop.first %}
                <div class="card {{ 'main' if is_main else '' }}" style="border-left-color: {{ colors.get(char.class, '#444') }}">
                    <div class="ilvl">{{ char.ilvl }}</div>
                    <span class="label" style="color: {{ colors.get(char.class, '#fff') }}">
                        {{ '⭐ MAIN' if is_main else 'TWINK' }}
                    </span>
                    <div style="margin-top:10px;">
                        <strong style="font-size: 1.2rem;">{{ char.name }}</strong><br>
                        <small>{{ char.class }} - {{ char.realm }}</small>
                    </div>
                    <div style="margin-top:15px; border-top: 1px solid #333; padding-top:10px;">
                        <a href="{{ char.rio_url }}" target="_blank" class="btn-rio">Raider.io ↗</a>
                        {% if is_admin %}
                        <a href="/delete/{{uid}}/{{loop.index0}}" style="color:#ff4d4d; float:right; text-decoration:none; font-size:0.8rem;" onclick="return confirm('Löschen?')">Löschen</a>
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
