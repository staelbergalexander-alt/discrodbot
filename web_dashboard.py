import os
import json
from quart import Quart, render_template_string, redirect, url_for, request
from quart_discord import DiscordOAuth2Session, requires_authorization, Unauthorized

app = Quart(__name__)

# Railway Variablen
app.secret_key = os.getenv("SECRET_KEY", "super-geheim")
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")

discord_auth = DiscordOAuth2Session(app)
DB_FILE = "/app/data/mitglieder_db.json"
OFFIZIER_ROLLE_ID = int(os.getenv("OFFIZIER_ROLLE_ID") or 0)

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
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

@app.route("/login")
async def login():
    return await discord_auth.create_session()

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
        # Admin-Check: Hat der User die Offizier-Rolle?
        # (Wir prüfen hier vereinfacht über eine Liste von IDs oder Rollen)
        # Für den Anfang: Du als Ersteller bist immer Admin
        if str(user.id) == "DEINE_DISCORD_ID_HIER": # Setze hier deine ID ein
            is_admin = True

    db = load_db()
    return await render_template_string(HTML_TEMPLATE, db=db, colors=CLASS_COLORS, user=user, is_logged_in=is_logged_in, is_admin=is_admin)

@app.route("/add", methods=["POST"])
@requires_authorization
async def add_char():
    user = await discord_auth.fetch_user()
    # Hier Prüfung einbauen, ob User Admin/Offizier ist
    form = await request.form
    db = load_db()
    uid = str(user.id)
    if uid not in db: db[uid] = {"chars": []}
    
    db[uid]["chars"].append({
        "name": form.get("name").capitalize(),
        "class": form.get("class"),
        "realm": form.get("realm", "Blackhand").capitalize()
    })
    save_db(db)
    return redirect(url_for("index"))

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Gilden Admin Tool</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #121212; color: #eee; padding: 40px; }
        .card { background: #1e1e1e; padding: 20px; border-radius: 10px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border-left: 5px solid #444; }
        .btn { padding: 10px 20px; border-radius: 5px; text-decoration: none; cursor: pointer; border: none; font-weight: bold; }
        .btn-login { background: #5865F2; color: white; }
        .btn-add { background: #3ba55c; color: white; }
        .admin-section { background: #2f3136; padding: 20px; border-radius: 10px; margin-bottom: 30px; }
        input, select { padding: 10px; background: #40444b; border: 1px solid #222; color: white; border-radius: 5px; margin-right: 10px; }
    </style>
</head>
<body>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px;">
        <h1>🛡️ Gilden-Verwaltung</h1>
        {% if not is_logged_in %}
            <a href="/login" class="btn btn-login">Mit Discord einloggen</a>
        {% else %}
            <span>Eingeloggt als <strong>{{ user.name }}</strong></span>
        {% endif %}
    </div>

    {% if is_admin %}
    <div class="admin-section">
        <h3>Neuen Charakter eintragen</h3>
        <form action="/add" method="post">
            <input type="text" name="name" placeholder="Name" required>
            <select name="class">
                {% for cname in colors.keys() %}<option value="{{cname}}">{{cname}}</option>{% endfor %}
            </select>
            <input type="text" name="realm" placeholder="Blackhand">
            <button type="submit" class="btn btn-add">Hinzufügen</button>
        </form>
    </div>
    {% endif %}

    <div class="list">
        {% for uid, data in db.items() %}
            {% for char in data.chars %}
            <div class="card" style="border-left-color: {{ colors.get(char.class, '#444') }}">
                <span><strong>{{ char.name }}</strong> - {{ char.class }} ({{ char.realm }})</span>
            </div>
            {% endfor %}
        {% endfor %}
    </div>
</body>
</html>
"""

async def run_web():
    port = int(os.getenv("PORT", 5000))
    await app.run_task(host="0.0.0.0", port=port)
