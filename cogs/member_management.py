import discord
from discord.ext import commands
import json
import os

class MemberManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/mitglieder_db.json"

    def update_json(self, member, status="Aktiv"):
        # Sicherstellen, dass der Ordner existiert
        os.makedirs("data", exist_ok=True)
        
        # Bestehende Daten laden
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except:
                    data = {"members": {}}
        else:
            data = {"members": {}}

        # Mitglied hinzufügen/aktualisieren
        data["members"][str(member.id)] = {
            "name": member.name,
            "status": status,
            "joined_at": str(member.joined_at)
        }

        # Speichern
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.update_json(member)
        print(f"{member.name} wurde zur Datenbank hinzugefügt.")

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_members(self, ctx):
        """Fügt alle aktuellen Server-Mitglieder zur JSON hinzu."""
        for member in ctx.guild.members:
            if not member.bot:
                self.update_json(member)
        await ctx.send("✅ Alle Mitglieder wurden mit dem Dashboard synchronisiert!")

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))