import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import urllib.parse
import re
import aiohttp
from datetime import datetime
from config import FORUM_CHANNEL_ID, DB_FILE

class MemberManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DB_FILE

    def load_data(self):
        os.makedirs("data", exist_ok=True)
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if "members" in data:
                        return data["members"]
                    return data
                except:
                    return {}
        return {}

    def save_data(self, data):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
    def parse_raiderio_url(self, url):
        """Extrahiert Name und Server und decodiert Sonderzeichen."""
        decoded_url = urllib.parse.unquote(url)
        match = re.search(r"characters/(?P<region>\w+)/(?P<realm>[\w-]+)/(?P<name>[\w-]+)", decoded_url)
        if match:
            return {
                "name": match.group("name"),
                "realm": match.group("realm"),
                "region": match.group("region")
            }
        return None

    @app_commands.command(name="twink_add_rio", description="Fügt einen weiteren Charakter zum Profil hinzu")
    @app_commands.describe(
        main_id="Die Discord ID des Besitzers (Nur Zahlen!)",
        rio_url="Der komplette Raider.io Link"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def twink_add_rio(self, interaction: discord.Interaction, main_id: str, rio_url: str):
        await interaction.response.defer(ephemeral=True)
        
        clean_id = "".join(filter(str.isdigit, main_id))
        data = self.load_data()
        
        char_info = self.parse_raiderio_url(rio_url)
        if not char_info:
            return await interaction.followup.send("❌ Ungültiger Raider.io Link!")

        char_class = "Unbekannt"
        async with aiohttp.ClientSession() as session:
            api_url = f"https://raider.io/api/v1/characters/profile?region={char_info['region']}&realm={char_info['realm']}&name={char_info['name']}"
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    api_data = await resp.json()
                    char_class = api_data.get('class', 'Unbekannt')
                    char_info['name'] = api_data.get('name', char_info['name'])
                    char_info['realm'] = api_data.get('realm', char_info['realm'])

        if clean_id not in data:
            data[clean_id] = {"chars": [], "real_name": "Unbekannt", "join_date": datetime.now().strftime("%d.%m.%Y")}
        
        if "chars" not in data[clean_id]:
            data[clean_id]["chars"] = []

        if any(c.get('name').lower() == char_info['name'].lower() for c in data[clean_id]["chars"]):
            return await interaction.followup.send("⚠️ Dieser Charakter ist bereits eingetragen.")

        data[clean_id]["chars"].append({
            "name": char_info["name"],
            "realm": char_info["realm"]
        })
        self.save_data(data)

        await self.send_twink_info_to_forum(interaction, clean_id, char_info, char_class, data[clean_id])
        await interaction.followup.send(f"✅ **{char_info['name']}** wurde zu <@{clean_id}> hinzugefügt!")

    async def send_twink_info_to_forum(self, interaction, member_id, char_info, char_class, user_data):
        forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if not forum:
            return

        real_name = user_data.get("real_name", "Unbekannt")
        target_thread = None
        
        # Suche nach dem Thread (per ID im Namen oder gespeicherter Thread-ID)
        for thread in forum.threads:
            if str(member_id) in thread.name:
                target_thread = thread
                break
        
        if not target_thread:
            target_thread = await forum.create_thread(
                name=f"Eintrag: {real_name} | {member_id}", 
                content=f"Profil für <@{member_id}>"
            )

        wcl_link = f"https://www.warcraftlogs.com/character/eu/{char_info['realm']}/{char_info['name']}"
        rio_link = f"https://raider.io/characters/eu/{char_info['realm']}/{char_info['name']}"

        embed = discord.Embed(
            title=f"🛡️ Zusätzlicher Charakter: {char_info['name']}", 
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Klasse", value=char_class, inline=True)
        embed.add_field(name="Spieler", value=real_name, inline=True)
        embed.add_field(name="Server", value=char_info['realm'].capitalize(), inline=False)
        embed.add_field(
            name="Links", 
            value=f"[Raider.io]({rio_link}) | [WarcraftLogs]({wcl_link})", 
            inline=False
        )
        
        owner = interaction.guild.get_member(int(member_id))
        footer_text = f"Twink von {owner.display_name}" if owner else f"Twink von {real_name}"
        embed.set_footer(text=footer_text)

        await target_thread.send(embed=embed)

    @app_commands.command(name="member_remove", description="Löscht einen Member komplett aus der DB")
    @app_commands.checks.has_permissions(administrator=True)
    async def member_remove(self, interaction: discord.Interaction, member_id: str):
        clean_id = "".join(filter(str.isdigit, member_id))
        data = self.load_data()
        
        if clean_id in data:
            del data[clean_id]
            self.save_data(data)
            await interaction.response.send_message(f"🗑️ User `{clean_id}` wurde gelöscht.")
        else:
            await interaction.response.send_message("❌ ID nicht gefunden.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MemberManagement(bot))