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

    async def update_nickname(self, interaction: discord.Interaction, member: discord.Member, new_char_name: str):
        """Hilfsfunktion: Ändert nur den Charakter-Teil im Format 'Char | Name'."""
        current_nick = member.display_name
        
        if "|" in current_nick:
            parts = current_nick.split("|", 1)
            real_name = parts[1].strip()
            new_nick = f"{new_char_name} | {real_name}"
        else:
            # Falls kein Trenner da ist, hängen wir den alten Namen als Real-Name an
            new_nick = f"{new_char_name} | {current_nick}"

        if len(new_nick) > 32:
            new_nick = new_nick[:32]

        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            print(f"Konnte Nickname für {member.display_name} nicht ändern (Fehlende Rechte).")

    @app_commands.command(name="set_main", description="Setzt den Hauptcharakter und passt den Discord-Namen an")
    @app_commands.describe(char_name="Name des Charakters", user="Optional: Das Mitglied, dessen Main geändert werden soll")
    async def set_main(self, interaction: discord.Interaction, char_name: str, user: discord.Member = None):
        db = self.load_db()
        target_user = user if user else interaction.user
        uid = str(target_user.id)

        if user and user != interaction.user:
            if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
                return await interaction.response.send_message("❌ Nur Offiziere dürfen den Main anderer ändern.", ephemeral=True)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message(f"❌ Keine Charaktere für {target_user.display_name} gefunden.", ephemeral=True)

        chars = db[uid]["chars"]
        main_char = next((c for c in chars if c['name'].lower() == char_name.lower()), None)

        if not main_char:
            return await interaction.response.send_message(f"❌ Charakter `{char_name}` nicht gefunden.", ephemeral=True)

        chars.remove(main_char)
        chars.insert(0, main_char)
        db[uid]["chars"] = chars
        self.save_db(db)
        
        await self.update_nickname(interaction, target_user, main_char['name'])
        await interaction.response.send_message(f"👑 **{main_char['name']}** ist nun der Main von {target_user.mention}. Discord-Name wurde angepasst!")

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
                if i == 0: is_main = True
                break
        
        if updated:
            self.save_db(db)
            if is_main:
                await self.update_nickname(interaction, interaction.user, neuer_name.capitalize())
            await interaction.response.send_message(f"✅ Umbenannt in `{neuer_name.capitalize()}`.")
        else:
            await interaction.response.send_message(f"❌ Nicht gefunden.", ephemeral=True)

   @app_commands.command(name="add_char", description="Fügt einen Charakter via Raider.IO Link hinzu und erkennt die Klasse")
    async def add_char(self, interaction: discord.Interaction, user: discord.Member, rio_link: str):
        if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur für Offiziere!", ephemeral=True)
            
        # Regex um Realm und Name aus dem Link zu extrahieren
        match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
        if not match:
            return await interaction.response.send_message("❌ Ungültiger Raider.IO Link.", ephemeral=True)
            
        srv, name = match.group(1), match.group(2)
        
        # Sofortige Antwort, da die API-Abfrage einen Moment dauern kann
        await interaction.response.defer()

        # Raider.IO API Abfrage
        import aiohttp
        api_url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}&fields=gear"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    return await interaction.followup.send(f"❌ Charakter `{name.capitalize()}` konnte bei Raider.IO nicht gefunden werden.")
                
                data = await response.json()
                char_class = data.get('class', 'Unbekannt')
                thumbnail = data.get('thumbnail_url')

        # Datenbank-Logik
        db = self.load_db()
        uid = str(user.id)
        srv_cap, name_cap = srv.capitalize(), name.capitalize()
        
        if uid not in db:
            db[uid] = {"chars": []}
        
        if any(c['name'] == name_cap and c['realm'] == srv_cap for c in db[uid]['chars']):
            return await interaction.followup.send("⚠️ Dieser Charakter ist bereits registriert.")
        
        # Speichern inklusive Klasse
        db[uid]["chars"].append({
            "name": name_cap, 
            "realm": srv_cap, 
            "class": char_class
        })
        
        # Falls es der erste Char ist, Nickname setzen
        if len(db[uid]["chars"]) == 1:
            await self.update_nickname(interaction, user, name_cap)
        
        self.save_db(db)

        # Bestätigungs-Embed
        embed = discord.Embed(title="✅ Charakter registriert", color=discord.Color.green())
        embed.add_field(name="Charakter", value=f"{name_cap}-{srv_cap}", inline=True)
        embed.add_field(name="Klasse", value=char_class, inline=True)
        embed.add_field(name="Mitglied", value=user.mention, inline=False)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="delete_char", description="Löscht einen Charakter aus der Datenbank")
    @app_commands.describe(char_name="Name des zu löschenden Charakters", user="Optional: Das Mitglied (nur für Offiziere)")
    async def delete_char(self, interaction: discord.Interaction, char_name: str, user: discord.Member = None):
        db = self.load_db()
        target_user = user if user else interaction.user
        uid = str(target_user.id)

        # Berechtigungs-Check
        if user and user != interaction.user:
            if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
                return await interaction.response.send_message("❌ Nur Offiziere dürfen Charaktere anderer löschen.", ephemeral=True)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message(f"❌ Keine Charaktere für {target_user.display_name} gefunden.", ephemeral=True)

        chars = db[uid]["chars"]
        char_to_remove = next((c for c in chars if c['name'].lower() == char_name.lower()), None)

        if not char_to_remove:
            return await interaction.response.send_message(f"❌ Charakter `{char_name}` wurde in der Liste nicht gefunden.", ephemeral=True)

        # Prüfen, ob der gelöschte Char der Main war (Index 0)
        was_main = (chars.index(char_to_remove) == 0)

        # Entfernen
        chars.remove(char_to_remove)
        
        message = f"🗑️ Charakter `{char_to_remove['name']}` wurde für {target_user.mention} gelöscht."

        if chars:
            db[uid]["chars"] = chars
            # Wenn der Main gelöscht wurde, wird der neue erste Char zum Main -> Nickname Update
            if was_main:
                new_main = chars[0]['name']
                await self.update_nickname(interaction, target_user, new_main)
                message += f"\n👑 Neuer Main ist nun `{new_main}`. Discord-Name wurde angepasst."
        else:
            # Falls gar kein Char mehr übrig ist
            del db[uid]
            message += "\n⚠️ Keine weiteren Charaktere übrig. Eintrag wurde komplett entfernt."

        self.save_db(db)
        await interaction.response.send_message(message)

    @app_commands.command(name="list_chars", description="Zeigt alle Charaktere eines Mitglieds an")
    @app_commands.describe(user="Das Mitglied, dessen Charaktere du sehen möchtest")
    async def list_chars(self, interaction: discord.Interaction, user: discord.Member = None):
        db = self.load_db()
        target_user = user if user else interaction.user
        uid = str(target_user.id)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message(f"❌ Keine Charaktere für {target_user.display_name} gefunden.", ephemeral=True)

        chars = db[uid]["chars"]
        
        embed = discord.Embed(
            title=f"Charaktere von {target_user.display_name}",
            color=discord.Color.green()
        )
        
        char_liste = ""
        for i, char in enumerate(chars):
            prefix = "👑 **(Main)**" if i == 0 else "🔹 (Twink)"
            char_liste += f"{prefix} {char['name']} - {char['realm']}\n"
        
        embed.description = char_liste
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="klassenliste", description="Zeigt eine Übersicht aller Charaktere sortiert nach Klassen")
    async def klassenliste(self, interaction: discord.Interaction):
        db = self.load_db()
        if not db:
            return await interaction.response.send_message("Die Datenbank ist leer.", ephemeral=True)

        # Klassen-Dictionary vorbereiten
        klassen_mapping = {}

        for uid, data in db.items():
            member = interaction.guild.get_member(int(uid))
            member_name = member.display_name if member else f"User {uid}"
            
            for char in data.get('chars', []):
                # Wir nehmen die Klasse aus der DB, falls nicht vorhanden "Unbekannt"
                klasse = char.get('class', 'Unbekannt').capitalize()
                
                if klasse not in klassen_mapping:
                    klassen_mapping[klasse] = []
                
                # Markierung ob Main oder Twink für die Liste
                is_main = (data['chars'].index(char) == 0)
                prefix = "👑" if is_main else "🔹"
                
                klassen_mapping[klasse].append(f"{prefix} {char['name']} ({member_name})")

        # Embed erstellen
        embed = discord.Embed(title="🛡️ Gilden-Klassenübersicht", color=discord.Color.gold())
        
        # Sortierte Ausgabe nach Klassennamen
        for klasse in sorted(klassen_mapping.keys()):
            chars_str = "\n".join(klassen_mapping[klasse])
            embed.add_field(name=f"**{klasse}**", value=chars_str, inline=True)

        await interaction.response.send_message(embed=embed)

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
                main_char = chars[0]['name']
                twinks_count = len(chars) - 1
                twink_info = f" (+{twinks_count} Twinks)" if twinks_count > 0 else ""
                desc += f"👤 {name} — 👑 **{main_char}**{twink_info}\n"
        
        embed.description = desc or "Keine Mitglieder in der Datenbank."
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))
