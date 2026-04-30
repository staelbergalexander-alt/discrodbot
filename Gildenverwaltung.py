import discord
from discord.ext import commands
import os
import asyncio
import json
from dotenv import load_dotenv

# Importiere die Webserver-Funktion aus deiner web_dashboard.py
from web_dashboard import run_web

load_dotenv()

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # Wichtig für Rollen-Zuweisung
        intents.message_content = True  # Wichtig für Commands
        
        super().__init__(
            command_prefix='!', 
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """Lädt Cogs, registriert persistente Views und startet den Webserver."""
        
        # 1. Liste deiner Cogs
        extensions = [
            'cogs.utilities', 
            'cogs.recruitment', 
            'cogs.member_management', 
            'cogs.dashboard',
            'cogs.poll',
            'cogs.raid_bot',
            'cogs.kader_io'
        ]
        """'cogs.logs_archiv'"""
        print("--- Lade Cogs ---")
        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"✅ Cog geladen: {ext}")
            except Exception as e:
                print(f"❌ Fehler bei {ext}: {e}")
        
        # 2. PERSISTENTE VIEWS REGISTRIEREN
        # Hier sagen wir dem Bot, dass er dauerhaft auf die Umfrage-Buttons achten soll.
        try:
            from cogs.utilities import RaidPollView
            from cogs.raid_bot import RaidView, AdminControlView
            from cogs.poll import DynamicPollView, DATA_FILE
            
            # Statische Views registrieren
            self.add_view(RaidPollView())
            self.add_view(RaidView())
            self.add_view(AdminControlView())
                        # --- DYNAMISCHE UMFRAGEN REAKTIVIEREN ---
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r") as f:
                    polls = json.load(f)
                    for msg_id, settings in polls.items():
                        # Wir laden die Optionen aus den gespeicherten Daten
                        options = list(settings["results"].keys())
                        # Registriere die View für jede Nachricht einzeln
                        self.add_view(DynamicPollView(msg_id, options))
                print(f"✅ {len(polls)} dynamische Umfragen reaktiviert")
            
            print("✅ Persistente Views und Umfragen registriert")
        except Exception as e:
            print(f"⚠️ Fehler beim Registrieren der Views: {e}")

        # 3. Webserver im Hintergrund starten
        print("--- Starte Webserver ---")
        self.loop.create_task(run_web(self))

    async def on_ready(self):
        print(f'✅ Bot online als {self.user.name}')

# --- Bot Instanz erstellen ---
bot = GildenBot()

# --- Sync Command ---
@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
        # Synchronisiert Slash-Commands (/) global
        fmt = await bot.tree.sync()
        await ctx.send(f"✅ {len(fmt)} Slash-Commands synchronisiert!")
    except Exception as e:
        await ctx.send(f"❌ Fehler beim Sync: {e}")

# --- Start Prozess ---
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("❌ Kein Token gefunden!")