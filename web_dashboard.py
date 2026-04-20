import os
import json
from quart import Quart, render_template_string, redirect, url_for, request
from quart_discord import DiscordOAuth2Session, requires_authorization, Unauthorized

app = Quart(__name__)

# Railway Umgebungsvariablen
app.secret_key = os.getenv("SECRET_KEY", "ein_sehr_geheimer_schluessel")
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true" # Nur für Entwicklung, Railway nutzt HTTPS

app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI") # DeineURL/callback

discord_auth = DiscordOAuth2Session(app)
DB_FILE = "/app/data/mitglieder_db.json"
OFFIZIER_ROLLE_ID = int(os.getenv("OFFIZIER_ROLLE_ID") or 0)

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {}

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
    is_offizier = False
    
    if is_logged_in:
        user = await discord_auth.fetch_user()
        # Prüfen, ob der User die Offizier-Rolle hat
        guilds = await discord_auth.fetch_guilds()
        # Hinweis: Um Rollen zu prüfen, müsste man über den Bot-Client gehen. 
        # Vereinfacht prüfen wir hier, ob der User eingeloggt ist.
    
    db = load_db()
    return await render_template_string(HTML_TEMPLATE, db=db, user=user, is_logged_in=is_logged_in)

@app.route("/add", methods=["POST"])
@requires_authorization
async def add():
    # Hier Logik zum Speichern einfügen...
    return redirect(url_for("index"))

# (Hier kommen die Styles und das HTML von vorhin rein, nur mit Login-Button)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Gilden Dashboard</title></head>
<body style="background:#121212; color:white; font-family:sans-serif; padding:40px;">
    {% if not is_logged_in %}
        <a href="/login" style="background:#7289da; color:white; padding:10px; text-decoration:none; border-radius:5px;">Mit Discord einloggen</a>
    {% else %}
        <p>Eingeloggt als {{ user.name }}#{{ user.discriminator }}</p>
        {% endif %}
</body>
</html>
"""

async def run_web():
    port = int(os.getenv("PORT", 5000))
    await app.run_task(host="0.0.0.0", port=port)
