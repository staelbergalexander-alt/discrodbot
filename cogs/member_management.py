import discord
from discord.ext import commands
from discord import app_commands
import json
import os

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

    def ensure_member(self, data, member: discord.Member):
        """Hilfsfunktion: Stellt sicher, dass ein Member in der DB existiert."""
        m_id = str(member.id)
        if m_id not in data["members"]:
            data["members"][m_id] = {
                "name": member.name,
                "status": "Aktiv",
                "joined_at": str(member.joined_at),
                "is_twink": False,
                "main_account_id": None,
                "twinks": []
            }
        return data

    @app_commands.command(name="twink_add", description="Verknüpft einen Twink mit einem Hauptaccount")
    @app_commands.checks.has_permissions(administrator=True)
    async def twink_add(self, interaction: discord.Interaction, main: discord.Member, twink: discord.Member):
        data = self.load_data()
        data = self.ensure_member(data, main)
        data = self.ensure_member(data, twink)

        twink_id = str(twink.id)
        main_id = str(main.id)

        if twink_id not in data["members"][main_id]["twinks"]:
            data["members"][main_id]["twinks"].append(twink_id)
        
        data["members"][twink_id]["is_twink"] = True
        data["members"][twink_id]["main_account_id"] = main_id

        self.save_data(data)
        await interaction.response.send_message(f"✅ **{twink.name}** wurde als Twink von **{main.name}** hinzugefügt.")

    @app_commands.command(name="member_edit", description="Bearbeitet den Status eines Mitglieds")
    @app_commands.checks.has_permissions(administrator=True)
    async def member_edit(self, interaction: discord.Interaction, member: discord.Member, status: str):
        data = self.load_data()
        m_id = str(member.id)

        if m_id in data["members"]:
            old_status = data["members"][m_id]["status"]
            data["members"][m_id]["status"] = status
            self.save_data(data)
            await interaction.response.send_message(f"📝 Status von **{member.name}** geändert: `{old_status}` ➔ `{status}`")
        else:
            await interaction.response.send_message("❌ Mitglied nicht in der Datenbank gefunden.", ephemeral=True)

    @app_commands.command(name="twink_remove", description="Löst die Twink-Verbindung auf")
    @app_commands.checks.has_permissions(administrator=True)
    async def twink_remove(self, interaction: discord.Interaction, twink: discord.Member):
        data = self.load_data()
        twink_id = str(twink.id)

        if twink_id in data["members"] and data["members"][twink_id]["is_twink"]:
            main_id = data["members"][twink_id]["main_account_id"]
            
            # Aus der Liste des Hauptaccounts entfernen
            if main_id and main_id in data["members"]:
                data["members"][main_id]["twinks"].remove(twink_id)
            
            # Twink-Status zurücksetzen
            data["members"][twink_id]["is_twink"] = False
            data["members"][twink_id]["main_account_id"] = None
            
            self.save_data(data)
            await interaction.response.send_message(f"🗑️ Die Verbindung für **{twink.name}** wurde gelöscht. Er wird nun als Main geführt.")
        else:
            await interaction.response.send_message("❌ Dieser User ist nicht als Twink markiert.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        data = self.load_data()
        data = self.ensure_member(data, member)
        self.save_data(data)
        print(f"Datenbank-Check: {member.name} ist bereit.")

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))