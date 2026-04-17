import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import re

DB_FILE = "/app/data/mitglieder_db.json"
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)

class MemberManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def load_db(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_db(self, data):
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)

    # --- 1. SET MAIN BEFEHL ---
    @app_commands.command(name="set_main", description="Setzt einen deiner Charaktere als Hauptcharakter (Main)")
    async def set_main(self, interaction: discord.Interaction, char_name: str):
        db = self.load_db()
        uid = str(interaction.user.id)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message("❌ Du hast noch keine Charaktere registriert.", ephemeral=True)

        chars = db[uid]["chars"]
        # Suche den Charakter (Case-insensitive)
        main_char = next((c for c in chars if c['name'].lower() == char_name.lower()), None)

        if not main_char:
            return await interaction.response.send_message(f"❌ Charakter `{char_name}` nicht in deiner Liste gefunden.", ephemeral=True)

        # Den Char an Position 0 schieben
        chars.remove(main_char)
        chars.insert(0, main_char)
        
        db[uid]["chars"] = chars
        self.save_db(db)
        
        await interaction.response.send_message(f"👑 **{main_char['name']}** wurde als dein Main festgelegt und wird im Dashboard priorisiert!")

    # --- 2. RENAME CHAR BEFEHL ---
    @app_commands.command(name="rename_char", description="Ändert den Namen eines registrierten Charakters")
    async def rename_char(self, interaction: discord.Interaction, alter_name: str, neuer_name: str):
        db = self.load_db()
        uid = str(interaction.user.id)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message("❌ Keine Charaktere gefunden.", ephemeral=True)

        updated = False
        for char in db[uid]["chars"]:
            if char['name'].lower() == alter_name.lower():
                char['name'] = neuer_name.capitalize()
                updated = True
                break
        
        if updated:
            self.save_db(db)
            await interaction.response.send_message(f"✅ Charakter `{alter_name}` wurde erfolgreich in `{neuer_name.capitalize()}` umbenannt.")
        else:
            await interaction.response.send_message(f"❌ Charakter `{alter_name}` nicht gefunden.", ephemeral=True)

    # --- BESTEHENDE BEFEHLE (ADD / REMOVE / LIST) ---
    @app_commands.command(name="add_char")
    async def add_char(self, interaction: discord.Interaction, user: discord.Member, rio_link: str):
        if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Nur für Offiziere!", ephemeral=True)
            
        match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
        if match:
            srv, name = match.group(1).capitalize(), match.group(2).capitalize()
            db = self.load_db()
            uid = str(user.id)
            if uid not in db: db[uid] = {"chars": []}
            
            if any(c['name'] == name and c['realm'] == srv for c in db[uid]['chars']):
                return await interaction.response.send_message("Charakter bereits da!", ephemeral=True)
            
            db[uid]["chars"].append({"name": name, "realm": srv})
            self.save_db(db)
            await interaction.response.send_message(f"✅ {name}-{srv} für {user.display_name} hinzugefügt!")

    @app_commands.command(name="memberliste")
    async def memberliste(self, interaction: discord.Interaction):
        db = self.load_db()
        embed = discord.Embed(title="📋 Gilden-Mitglieder", color=discord.Color.blue())
        desc = ""
        for uid, data in db.items():
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            chars = ", ".join([f"{c['name']}" for c in data.get('chars', [])])
            desc += f"👤 **{name}**: {chars}\n"
        embed.description = desc or "Leer."
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))
