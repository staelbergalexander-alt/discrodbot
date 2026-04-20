import discord
from discord.ext import commands
import os
import asyncio
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
        """Lädt Cogs und startet den Webserver."""
        # Liste deiner Cogs (Dateinamen ohne .py)
        # Wenn die Dateien im Ordner "cogs" liegen, ist der Punkt-Pfad richtig
        extensions = [
            'cogs.utilities', 
            'cogs.recruitment', 
            'cogs.member_management', 
            'cogs.dashboard', 
            'cogs.logs_archiv'
        ]
        
        print("--- Lade Cogs ---")
        for ext in extensions:
            try:
                # Wir laden die Extension direkt. 
                # Falls sie nicht existiert, fängt der except-Block den Fehler ab.
                await self.load_extension(ext)
                print(f"✅ Cog geladen: {ext}")
            except Exception as e:
                print(f"❌ Fehler bei {ext}: {e}")
        
        # Webserver im Hintergrund starten
        if bot_instance := self:
            self.loop.create_task(run_web(bot_instance))

    async def on_ready(self):
        print(f'✅ Bot online als {self.user.name}')

# --- Bot Instanz erstellen ---
bot = GildenBot()

# --- Sync Command (jetzt nach der Erstellung von 'bot') ---
@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
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