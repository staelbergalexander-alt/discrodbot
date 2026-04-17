import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
from datetime import datetime

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Hier starten wir die automatische Aktualisierung
        self.refresh_dashboard.start()

    def cog_unload(self):
        self.refresh_dashboard.cancel()

    @tasks.loop(minutes=30)
    async def refresh_dashboard(self):
        # Warte bis der Bot eingeloggt ist
        await self.bot.wait_until_ready()
        print("Dashboard-Update wird ausgeführt...")
        # Hier kommt deine Logik zum iLvl-Check rein (wie vorher besprochen)

    @app_commands.command(name="setup_dashboard", description="Erstellt das Raid-Dashboard")
    async def setup_dashboard(self, interaction: discord.Interaction):
        # Prüfen ob der User Offizier ist
        OFFIZIER_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
        if any(r.id == OFFIZIER_ID for r in interaction.user.roles):
            await interaction.response.send_message("Dashboard wird initialisiert...", ephemeral=True)
            # Logik für das Dashboard-Embed hier...
        else:
            await interaction.response.send_message("Keine Berechtigung!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
