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
        .container { max-width: 1000px; margin: auto; }
        .admin-panel { background: var(--card); padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid var(--cyan); }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
        .card { background: var(--card); padding: 15px; border-radius: 10px; border-left: 5px solid #444; position: relative; }
        .id-badge { font-size: 0.7rem; background: #000; padding: 2px 5px; border-radius: 4px; color: var(--cyan); }
    </style>
</head>
<body>
    <div class="container">
        <header style="display:flex; justify-content: space-between; margin-bottom:20px;">
            <h1>🛡️ Gilden Dashboard</h1>
            {% if is_logged_in %}<p>Hallo {{ user.name }}</p>{% else %}<a href="/login" style="color:var(--cyan);">Login</a>{% endif %}
        </header>

        {% if is_admin %}
        <div class="admin-panel">
            <form action="/add" method="post">
                <input type="text" name="rio_link" placeholder="Raider.io Link" required style="width:50%;">
                <input type="text" name="discord_id" placeholder="User ID (leer = eigene)" style="width:30%;">
                <button type="submit">OK</button>
            </form>
        </div>
        {% endif %}

        <div class="grid">
            {% for uid, data in db.items() %}
                {% for char in data.chars %}
                <div class="card" style="border-left-color: {{ colors.get(char.class, '#444') }}">
                    <strong style="font-size: 1.2rem;">{{ char.name }}</strong> ({{ char.ilvl }})<br>
                    <small>{{ char.class }} - {{ char.realm }}</small><br>
                    <div style="margin-top:10px; font-size:0.8rem; color:#888;">
                        Besitzer ID: <span class="id-badge">{{ uid }}</span>
                        {% if is_admin %}<a href="/delete/{{uid}}/{{loop.index0}}" style="color:red; float:right;">Löschen</a>{% endif %}
                    </div>
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
