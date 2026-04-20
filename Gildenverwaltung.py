import discord
from discord.ext import commands
import os
import json
import asyncio
from dotenv import load_dotenv

# Importiere die Webserver-Funktion aus deiner web_dashboard.py
from web_dashboard import run_web

# Lade Umgebungsvariablen (.env Datei)
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = int(os.getenv('SERVER_ID') or 0)

# Bot-Setup mit allen Berechtigungen (Intents)
intents = discord.Intents.default()
intents.members = True  # Wichtig, um Rollen und Mitglieder zu sehen
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Pfad zur Datenbank
DB_FILE = "data/mitglieder_db.json"

# Sicherstellen, dass der Ordner existiert
if not os.path.exists("data"):
    os.makedirs("data")

@bot.event
async def on_ready():
    print(f'✅ Bot eingeloggt als {bot.user.name}')
    print(f'🌐 Web-Dashboard sollte jetzt unter Port 5000 erreichbar sein.')

# Beispiel-Befehl zum Testen der Datenbank
@bot.command(name='sync_classes')
async def sync_classes(ctx):
    # Hier kommt deine Logik rein, um die JSON zu füllen
    # Dies ist nur ein Platzhalter für dein bestehendes System
    await ctx.send("Daten werden synchronisiert...")

# --- DER WICHTIGSTE TEIL: DER START-PROZESS ---

async def start_everything():
    """Startet den Bot und das Web-Dashboard gleichzeitig."""
    if not TOKEN:
        print("❌ FEHLER: Kein DISCORD_TOKEN in der .env oder den Umgebungsvariablen gefunden!")
        return

    try:
        # Wir starten beides parallel mit asyncio.gather
        # Wichtig: Wir übergeben 'bot' an run_web, damit das Dashboard 
        # die Rollen live abfragen kann!
        await asyncio.gather(
            run_web(bot),  
            bot.start(TOKEN)
        )
    except Exception as e:
        print(f"❌ Kritischer Fehler beim Starten: {e}")

if __name__ == "__main__":
    # Startet das gesamte System
    try:
        asyncio.run(start_everything())
    except KeyboardInterrupt:
        print("Stopping...")