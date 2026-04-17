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

    async def update_nickname(self, interaction: discord.Interaction, member: discord.Member, new_name: str):
        """Hilfsfunktion zum Ändern des Nicknamens."""
        try:
            await member.edit(nick=new_name)
        except discord.Forbidden:
            # Falls der Bot keine Rechte hat (z.B. bei Serverbesitzern)
            print(f"Konnte Nickname für {member.display_name} nicht ändern (Fehlende Rechte).")

    # --- 1. SET MAIN BEFEHL (mit User-Option & Nickname Update) ---
    @app_commands.command(name="set_main", description="Setzt den Hauptcharakter und passt den Discord-Namen an")
    @app_commands.describe(char_name="Name des Charakters", user="Optional: Das Mitglied, dessen Main geändert werden soll")
    async def set_main(self, interaction: discord.Interaction, char_name: str, user: discord.Member = None):
        db = self.load_db()
        target_user = user if user else interaction.user
        uid = str(target_user.id)

        # Offizier-Check, wenn man jemand anderen bearbeitet
        if user and user != interaction.user:
            if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
                return await interaction.response.send_message("❌ Nur Offiziere dürfen den Main anderer ändern.", ephemeral=True)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message(f"❌ Keine Charaktere für {target_user.display_name} gefunden.", ephemeral=True)

        chars = db[uid]["chars"]
        main_char = next((c for c in chars if c['name'].lower() == char_name.lower()), None)

        if not main_char:
            return await interaction.response.send_message(f"❌ Charakter `{char_name}` nicht gefunden.", ephemeral=True)

        # Datenbank-Update: Main an Position 0 schieben
        chars.remove(main_char)
        chars.insert(0, main_char)
        db[uid]["chars"] = chars
        self.save_db(db)
        
        # Nickname-Update
        await self.update_nickname(interaction, target_user, main_char['name'])
        
        await interaction.response.send_message(f"👑 **{main_char['name']}** ist nun der Main von {target_user.mention}. Discord-Name wurde angepasst!")

    # --- 2. RENAME CHAR BEFEHL ---
    @app_commands.command(name="rename_char", description="Ändert den Namen eines Charakters")
    async def rename_char(self, interaction: discord.Interaction, alter_name: str, neuer_name: str):
        db = self.load_db()
        uid = str(interaction.user.id)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message("❌ Keine Charaktere gefunden.", ephemeral=True)

        updated = False
        is_main = False
        for i, char in enumerate(db[uid]["chars"]):
            if char['name'].lower() == alter_name.lower():
                char['name'] = neuer_name.capitalize()
                updated = True
                if i == 0: is_main = True # Falls es der Main war, Nickname später ändern
                break
        
        if updated:
            self.save_db(db)
            if is_main:
                await self.update_nickname(interaction, interaction.user, neuer_name.capitalize())
            await interaction.response.send_message(f"✅ Umbenannt in `{neuer_name.capitalize()}`.")
        else:
            await interaction.response.send_message(f"❌ Nicht gefunden.", ephemeral=True)

    # --- ADD CHAR (mit Nickname-Check) ---
    @app_commands.command(name="add_char")
    async def add_char(self, interaction: discord.Interaction, user: discord.Member, rio_link: str):
        if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("Nur für Offiziere!", ephemeral=True)
            
        match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
        if match:
            srv, name = match.group(1).capitalize(), match.group(2).capitalize()
            db = self.load_db()
            uid = str(user.id)
            
            if uid not in db:
                db[uid] = {"chars": []}
            
            if any(c['name'] == name and c['realm'] == srv for c in db[uid]['chars']):
                return await interaction.response.send_message("Char bereits registriert.", ephemeral=True)
            
            db[uid]["chars"].append({"name": name, "realm": srv})
            
            # Falls es der erste Char ist, automatisch Nickname setzen
            if len(db[uid]["chars"]) == 1:
                await self.update_nickname(interaction, user, name)
            
            self.save_db(db)
            await interaction.response.send_message(f"✅ {name}-{srv} für {user.display_name} hinzugefügt!")

    # --- MEMBERLISTE (Nur Main-Charakter Fokus) ---
    @app_commands.command(name="memberliste", description="Zeigt die Gildenmitglieder und ihren Hauptcharakter")
    async def memberliste(self, interaction: discord.Interaction):
        db = self.load_db()
        embed = discord.Embed(title="📋 Gilden-Mains", color=discord.Color.blue())
        desc = ""
        
        for uid, data in db.items():
            member = interaction.guild.get_member(int(uid))
            name = member.mention if member else f"User {uid}"
            
            chars = data.get('chars', [])
            if chars:
                main_char = chars[0]['name'] # Der erste in der Liste ist der Main
                twinks_count = len(chars) - 1
                twink_info = f" (+{twinks_count} Twinks)" if twinks_count > 0 else ""
                desc += f"👤 {name} — 👑 **{main_char}**{twink_info}\n"
        
        embed.description = desc or "Keine Mitglieder in der Datenbank."
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))
