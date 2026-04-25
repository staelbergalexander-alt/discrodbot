import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re

class MemberManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/mitglieder_db.json"

    def load_data(self):
        os.makedirs("data", exist_ok=True)
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except:
                    return {"members": {}}
        return {"members": {}}

    def save_data(self, data):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def parse_raiderio_url(self, url):
        """Extrahiert Name und Server aus einem Raider.io Link."""
        # Beispiel: https://raider.io/characters/eu/blackhand/MeinChar
        match = re.search(r"characters/(?P<region>\w+)/(?P<realm>[\w-]+)/(?P<name>[\w-]+)", url)
        if match:
            return {
                "name": match.group("name").capitalize(),
                "realm": match.group("realm").capitalize(),
                "region": match.group("region").upper()
            }
        return None

    @app_commands.command(name="twink_add_rio", description="Fügt einen weiteren Charakter (Twink) zum Profil hinzu")
    @app_commands.describe(
        main_id="Die Discord ID des Besitzers",
        rio_url="Der komplette Raider.io Link des neuen Charakters"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def twink_add_rio(self, interaction: discord.Interaction, main_id: str, rio_url: str):
        data = self.load_data()
        
        char_info = self.parse_raiderio_url(rio_url)
        if not char_info:
            return await interaction.response.send_message("❌ Ungültiger Raider.io Link!", ephemeral=True)

        # 1. Sicherstellen, dass der User-Eintrag existiert
        if main_id not in data["members"]:
            data["members"][main_id] = {
                "name": "Unbekannt", 
                "status": "Aktiv", 
                "chars": [], # Wir nutzen eine Liste für alle Charaktere dieses Users
                "is_twink": False
            }

        # Falls das alte Format (ohne "chars" Liste) vorliegt, fixen wir das hier kurz
        if "chars" not in data["members"][main_id]:
            data["members"][main_id]["chars"] = []

        # 2. Prüfen, ob der Charakter schon existiert, um Dubletten zu vermeiden
        exists = any(c['rio_url'] == rio_url for c in data["members"][main_id]["chars"])
        
        if not exists:
            data["members"][main_id]["chars"].append({
                "name": char_info["name"],
                "realm": char_info["realm"],
                "rio_url": rio_url
            })
            self.save_data(data)
            await interaction.response.send_message(
                f"✅ **{char_info['name']}** wurde dem Profil von ID `{main_id}` hinzugefügt."
            )
        else:
            await interaction.response.send_message("⚠️ Dieser Charakter ist bereits für diesen User registriert.", ephemeral=True)

    @app_commands.command(name="member_remove", description="Löscht einen Member komplett aus der DB")
    @app_commands.checks.has_permissions(administrator=True)
    async def member_remove(self, interaction: discord.Interaction, member_id: str):
        data = self.load_data()
        if member_id in data["members"]:
            del data["members"][member_id]
            self.save_data(data)
            await interaction.response.send_message(f"🗑️ ID `{member_id}` wurde aus der Datenbank gelöscht.")
        else:
            await interaction.response.send_message("❌ ID nicht gefunden.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))