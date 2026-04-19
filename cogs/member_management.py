import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import re
import aiohttp

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
            new_nick = f"{new_char_name} | {current_nick}"

        if len(new_nick) > 32:
            new_nick = new_nick[:32]

        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            print(f"Rechte fehlen für Nickname-Update bei {member.display_name}")

    @app_commands.command(name="add_char", description="Fügt einen Charakter hinzu (Klasse wird automatisch erkannt)")
    async def add_char(self, interaction: discord.Interaction, user: discord.Member, rio_link: str):
        if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur für Offiziere!", ephemeral=True)
            
        match = re.search(r"characters/eu/([^/]+)/([^/?#\s]+)", rio_link.lower())
        if not match:
            return await interaction.response.send_message("❌ Ungültiger Raider.IO Link.", ephemeral=True)
            
        srv, name = match.group(1), match.group(2)
        await interaction.response.defer()

        api_url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={srv}&name={name}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status != 200:
                    return await interaction.followup.send(f"❌ Charakter `{name.capitalize()}` nicht gefunden.")
                data = await response.json()
                char_class = data.get('class', 'Unbekannt')

        db = self.load_db()
        uid = str(user.id)
        name_cap, srv_cap = name.capitalize(), srv.capitalize()
        
        if uid not in db:
            db[uid] = {"chars": []}
        
        if any(c['name'] == name_cap and c['realm'] == srv_cap for c in db[uid]['chars']):
            return await interaction.followup.send("⚠️ Bereits registriert.")
        
        db[uid]["chars"].append({"name": name_cap, "realm": srv_cap, "class": char_class})
        
        if len(db[uid]["chars"]) == 1:
            await self.update_nickname(interaction, user, name_cap)
            
        self.save_db(db)
        await interaction.followup.send(f"✅ **{name_cap}** ({char_class}) für {user.mention} hinzugefügt!")

    @app_commands.command(name="set_main", description="Setzt einen Charakter als Main")
    async def set_main(self, interaction: discord.Interaction, char_name: str, user: discord.Member = None):
        db = self.load_db()
        target_user = user if user else interaction.user
        uid = str(target_user.id)

        if user and user != interaction.user and not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Keine Rechte.", ephemeral=True)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message("❌ Keine Charaktere gefunden.", ephemeral=True)

        chars = db[uid]["chars"]
        main_char = next((c for c in chars if c['name'].lower() == char_name.lower()), None)

        if not main_char:
            return await interaction.response.send_message(f"❌ `{char_name}` nicht gefunden.", ephemeral=True)

        chars.remove(main_char)
        chars.insert(0, main_char)
        self.save_db(db)
        
        await self.update_nickname(interaction, target_user, main_char['name'])
        await interaction.response.send_message(f"👑 **{main_char['name']}** ist nun Main von {target_user.mention}.")

    @app_commands.command(name="list_chars", description="Zeigt alle Chars eines Users")
    async def list_chars(self, interaction: discord.Interaction, user: discord.Member = None):
        db = self.load_db()
        target_user = user if user else interaction.user
        uid = str(target_user.id)

        if uid not in db or not db[uid].get("chars"):
            return await interaction.response.send_message("❌ Keine Daten gefunden.", ephemeral=True)

        chars = db[uid]["chars"]
        embed = discord.Embed(title=f"Charaktere von {target_user.display_name}", color=discord.Color.blue())
        
        liste = ""
        for i, c in enumerate(chars):
            pref = "👑" if i == 0 else "🔹"
            liste += f"{pref} {c['name']} ({c.get('class', 'Unbekannt')})\n"
        
        embed.description = liste
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="klassenliste", description="Übersicht aller Klassen")
    async def klassenliste(self, interaction: discord.Interaction):
        db = self.load_db()
        if not db: return await interaction.response.send_message("DB leer.", ephemeral=True)

        mapping = {}
        for uid, data in db.items():
            member = interaction.guild.get_member(int(uid))
            m_name = member.display_name if member else f"User {uid}"
            for char in data.get('chars', []):
                kl = char.get('class', 'Unbekannt')
                if kl not in mapping: mapping[kl] = []
                is_m = (data['chars'].index(char) == 0)
                mapping[kl].append(f"{'👑' if is_m else '🔹'} {char['name']} ({m_name})")

        embed = discord.Embed(title="🛡️ Klassenübersicht", color=discord.Color.gold())
        for kl in sorted(mapping.keys()):
            embed.add_field(name=kl, value="\n".join(mapping[kl]), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sync_classes", description="Offiziere: Aktualisiert fehlende Klassen in der Datenbank via Raider.IO")
    async def sync_classes(self, interaction: discord.Interaction):
        # Nur Offiziere dürfen diesen schweren Befehl ausführen
        if not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur für Offiziere!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        db = self.load_db()
        updated_count = 0
        
        async with aiohttp.ClientSession() as session:
            for uid, data in db.items():
                for char in data.get('chars', []):
                    # Nur abfragen, wenn Klasse fehlt oder "Unbekannt" ist
                    if char.get('class') in [None, 'Unbekannt']:
                        name = char['name']
                        realm = char['realm']
                        
                        api_url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}"
                        
                        try:
                            async with session.get(api_url) as response:
                                if response.status == 200:
                                    res_data = await response.json()
                                    char['class'] = res_data.get('class', 'Unbekannt')
                                    updated_count += 1
                        except Exception as e:
                            print(f"Fehler beim Sync von {name}: {e}")
        
        if updated_count > 0:
            self.save_db(db)
            await interaction.followup.send(f"✅ Sync abgeschlossen! {updated_count} Charaktere wurden aktualisiert.")
        else:
            await interaction.followup.send("ℹ️ Alle Charaktere sind bereits auf dem neuesten Stand.")

    @app_commands.command(name="delete_char", description="Löscht einen Charakter")
    async def delete_char(self, interaction: discord.Interaction, char_name: str, user: discord.Member = None):
        db = self.load_db()
        target_user = user if user else interaction.user
        uid = str(target_user.id)

        if user and user != interaction.user and not any(r.id == OFFIZIER_ROLLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Keine Rechte.", ephemeral=True)

        if uid not in db: return await interaction.response.send_message("Nicht gefunden.", ephemeral=True)

        chars = db[uid]["chars"]
        char_to_del = next((c for c in chars if c['name'].lower() == char_name.lower()), None)

        if not char_to_del: return await interaction.response.send_message("Char nicht gefunden.", ephemeral=True)

        was_main = (chars.index(char_to_del) == 0)
        chars.remove(char_to_del)

        if chars:
            db[uid]["chars"] = chars
            if was_main:
                await self.update_nickname(interaction, target_user, chars[0]['name'])
        else:
            del db[uid]

        self.save_db(db)
        await interaction.response.send_message(f"🗑️ `{char_name}` gelöscht.")

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))
