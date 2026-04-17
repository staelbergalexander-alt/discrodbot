import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import re

# Pfad zur Datenbank
DB_FILE = "/app/data/mitglieder_db.json"
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)

class MemberManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Hilfsfunktion: Prüfen ob Offizier
    def is_offizier():
        def predicate(interaction: discord.Interaction):
            return any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles)
        return app_commands.check(predicate)

    def load_db(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_db(self, data):
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)

    @app_commands.command(name="add_char", description="Fügt einem User einen WoW-Charakter hinzu")
    @is_offizier()
    async def add_char(self, interaction: discord.Interaction, user: discord.Member, rio_link: str):
        match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
        if not match:
            return await interaction.response.send_message("❌ Ungültiger Raider.io Link!", ephemeral=True)

        srv, name = match.group(1).capitalize(), match.group(2).capitalize()
        db = self.load_db()
        uid = str(user.id)

        if uid not in db:
            db[uid] = {"chars": []}
        
        if any(c['name'] == name and c['realm'] == srv for c in db[uid]['chars']):
            return await interaction.response.send_message(f"⚠️ {name}-{srv} ist bereits für {user.display_name} registriert.", ephemeral=True)

        db[uid]["chars"].append({"name": name, "realm": srv})
        self.save_db(db)
        await interaction.response.send_message(f"✅ **{name}-{srv}** wurde für {user.mention} hinzugefügt.")

    @app_commands.command(name="remove_char", description="Entfernt einen Charakter oder einen ganzen User aus der DB")
    @is_offizier()
    async def remove_char(self, interaction: discord.Interaction, user: discord.Member, char_name: str = None):
        db = self.load_db()
        uid = str(user.id)

        if uid not in db:
            return await interaction.response.send_message("❌ Dieser User ist nicht in der Datenbank.", ephemeral=True)

        if char_name:
            # Nur einen bestimmten Charakter löschen
            original_count = len(db[uid]["chars"])
            db[uid]["chars"] = [c for c in db[uid]["chars"] if c['name'].lower() != char_name.lower()]
            
            if len(db[uid]["chars"]) == original_count:
                return await interaction.response.send_message(f"❌ Charakter `{char_name}` wurde bei {user.display_name} nicht gefunden.", ephemeral=True)
            
            self.save_db(db)
            await interaction.response.send_message(f"🗑️ Charakter `{char_name}` für {user.display_name} entfernt.")
        else:
            # Ganzen User löschen
            del db[uid]
            self.save_db(db)
            await interaction.response.send_message(f"🗑️ Alle Daten für {user.display_name} wurden aus der Datenbank gelöscht.")

    @app_commands.command(name="memberliste", description="Zeigt alle registrierten Mitglieder und ihre Charaktere")
    @is_offizier()
    async def memberliste(self, interaction: discord.Interaction):
        db = self.load_db()
        if not db:
            return await interaction.response.send_message("Die Datenbank ist leer.", ephemeral=True)

        embed = discord.Embed(title="📋 Gilden-Datenbank", color=discord.Color.blue())
        
        output = ""
        for uid, data in db.items():
            member = interaction.guild.get_member(int(uid))
            member_name = member.mention if member else f"Unbekannter User ({uid})"
            chars = ", ".join([f"{c['name']}" for c in data.get('chars', [])]) or "Keine Chars"
            output += f"👤 {member_name}\n└ 🎮 {chars}\n\n"

        if len(output) > 4000:
            output = output[:3900] + "... (Liste zu lang)"
        
        embed.description = output
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))
