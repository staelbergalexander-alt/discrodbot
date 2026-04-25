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
                    data = json.load(f)
                    # Falls die Datei im "alten" Format mit ["members"] ist, 
                    # ziehen wir die Daten eine Ebene nach oben
                    if "members" in data:
                        return data["members"]
                    return data
                except:
                    return {}
        return {}

    def save_data(self, data):
        # Wir speichern die Daten direkt als Dictionary
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

    @app_commands.command(name="twink_add_rio", description="Fügt einen weiteren Charakter zum Profil hinzu")
    @app_commands.describe(
        main_id="Die Discord ID des Besitzers",
        rio_url="Der komplette Raider.io Link"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def twink_add_rio(self, interaction: discord.Interaction, main_id: str, rio_url: str):
        data = self.load_data() # Lädt jetzt direkt das Dict
        
        char_info = self.parse_raiderio_url(rio_url)
        if not char_info:
            return await interaction.response.send_message("❌ Ungültiger Raider.io Link!", ephemeral=True)

        # User-Eintrag sicherstellen (flache Struktur wie im Web-Dashboard)
        if main_id not in data:
            data[main_id] = {"chars": []}
        
        if "chars" not in data[main_id]:
            data[main_id]["chars"] = []

        # Dubletten-Check
        if not any(c.get('rio_url') == rio_url for c in data[main_id]["chars"]):
            data[main_id]["chars"].append({
                "name": char_info["name"],
                "realm": char_info["realm"],
                "rio_url": rio_url
            })
            self.save_data(data)
            await interaction.response.send_message(f"✅ **{char_info['name']}** wurde hinzugefügt!")
        else:
            await interaction.response.send_message("⚠️ Charakter existiert bereits.", ephemeral=True)
            
    async def send_twink_info_to_forum(guild, member, char_data, real_name, join_date):
        forum = guild.get_channel(FORUM_CHANNEL_ID)
        if not forum:
        return

        # Design wie in deinem Screenshot
        embed = discord.Embed(
        title=f"🛡️ Neuer Twink: {char_data['name']}", 
        color=discord.Color.blue()
    )
    embed.add_field(name="Klasse", value=char_data['class'], inline=True)
    embed.add_field(name="Spieler", value=real_name, inline=True)
    embed.add_field(name="Server", value=char_data['realm'], inline=False)
    embed.add_field(name="Eintrittsdatum", value=join_date, inline=True)
    
    # Links generieren
    rio_url = f"https://raider.io/characters/eu/{char_data['realm']}/{char_data['name']}"
    wcl_url = f"https://www.warcraftlogs.com/character/eu/{char_data['realm']}/{char_data['name']}"
    embed.add_field(
        name="Links", 
        value=f"[Raider.io]({rio_url}) | [WarcraftLogs]({wcl_url})", 
        inline=False
    )
    embed.set_footer(text=f"Twink von {member.display_name}")

    # Im Forum posten (entweder neuer Thread oder Nachricht in bestehenden Thread)
    # Wenn du es im Bewerber-Thread haben willst, musst du die Thread-ID speichern.
    await forum.create_thread(name=f"Twink: {char_data['name']} | {real_name}", embed=embed)

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