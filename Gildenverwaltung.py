import discord
from discord.ext import commands
import os
import json
import asyncio
# Falls load_dotenv Fehler macht, nutzen wir einen Fallback
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass 

# Importiere die Webserver-Funktion aus deiner web_dashboard.py
from web_dashboard import run_web

# Variablen laden
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = int(os.getenv('SERVER_ID') or 0)

# Bot-Setup
intents = discord.Intents.default()
intents.members = True  
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot eingeloggt als {bot.user.name}')

# --- HIER KOMMT DEIN BESTEHENDER CODE (COMMANDS ETC.) REIN ---

# --- DER FIX FÜR DEN START-PROZESS ---

async def start_everything():
    """Diese Funktion kapselt die async-Aufrufe korrekt ein."""
    if not TOKEN:
        print("❌ FEHLER: Kein DISCORD_TOKEN gefunden!")
        return

    print("🚀 Starte Webserver und Bot...")
    # Beides gleichzeitig starten
    await asyncio.gather(
        run_web(bot),  
        bot.start(TOKEN)
    )

if __name__ == "__main__":
    # Das ist der einzige Weg, eine async-Funktion von 'außen' zu starten
    try:
        asyncio.run(start_everything())
    except KeyboardInterrupt:
        print("Wird beendet...")
    except Exception as e:
        print(f"Kritischer Fehler: {e}")