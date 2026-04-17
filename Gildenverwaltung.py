import discord
from discord.ext import commands
import os
import json

# IDs aus Railway laden
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
TOKEN = os.getenv('DISCORD_TOKEN')

class GildenBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    # Diese Funktion repariert das Datenbank-Format automatisch beim Start
    def check_db_format(self):
        db_path = "/app/data/mitglieder_db.json"
        if os.path.exists(db_path):
            with open(db_path, "r") as f:
                try: 
                    data = json.load(f)
                    updated = False
                    for uid in list(data.keys()):
                        # Fix für den KeyError: 'chars'
                        if isinstance(data[uid], dict) and "chars" not in data[uid]:
                            old_name = data[uid].get("name", "Unbekannt")
                            old_realm = data[uid].get("realm", "Blackhand")
                            data[uid] = {"chars": [{"name": old_name, "realm": old_realm}]}
                            updated = True
                    if updated:
                        with open(db_path, "w") as f_out:
                            json.dump(data, f_out, indent=4)
                        print("Datenbank-Format wurde aktualisiert.")
                except: print("Datenbank konnte nicht gelesen werden.")

    async def setup_hook(self):
        self.check_db_format()
        # Lädt alle Cogs aus dem Ordner
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'Cog geladen: {filename}')
        
        if SERVER_ID != 0:
            guild = discord.Object(id=SERVER_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

bot = GildenBot()
bot.run(TOKEN)
