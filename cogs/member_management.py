import discord
from discord.ext import commands
from discord import app_commands
import json
import os
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
                    # Migriert altes Format ["members"] auf flache Struktur
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
        """Extrahiert Name und Server aus einem Raider.io Link."""
        match = re.search(r"characters/(?P<region>\w+)/(?P<realm>[\w-]+)/(?P<name>[\w-]+)", url)
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
        
        # 1. ID bereinigen (Falls <@...> eingegeben wurde)
        clean_id = "".join(filter(str.isdigit, main_id))
        data = self.load_data()
        
        char_info = self.parse_raiderio_url(rio_url)
        if not char_info:
            return await interaction.followup.send("❌ Ungültiger Raider.io Link!")

        # 2. Daten von Raider.io abrufen für Klasse & korrekte Schreibweise
        char_class = "Unbekannt"
        async with aiohttp.ClientSession() as session:
            api_url = f"https://raider.io/api/v1/characters/profile?region={char_info['region']}&realm={char_info['realm']}&name={char_info['name']}"
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    api_data = await resp.json()
                    char_class = api_data.get('class', 'Unbekannt')
                    char_info['name'] = api_data.get('name', char_info['name'])
                    char_info['realm'] = api_data.get('realm', char_info['realm'])

        # 3. Datenbank-Eintrag aktualisieren
        if clean_id not in data:
            data[clean_id] = {"chars": [], "real_name": "Unbekannt", "join_date": datetime.now().strftime("%d.%m.%Y")}
        
        if "chars" not in data[clean_id]:
            data[clean_id]["chars"] = []

        # Dubletten-Check
        if any(c.get('name').lower() == char_info['name'].lower() for c in data[clean_id]["chars"]):
            return await interaction.followup.send("⚠️ Dieser Charakter ist bereits eingetragen.")

        data[clean_id]["chars"].append({
            "name": char_info["name"],
            "realm": char_info["realm"]
        })
        self.save_data(data)

        # 4. Forum-Post erstellen (Design wie gewünscht)
        await self.send_twink_info_to_forum(interaction, clean_id, char_info, char_class, data[clean_id])
        
        await interaction.followup.send(f"✅ **{char_info['name']}** wurde zu <@{clean_id}> hinzugefügt und im Forum gepostet!")

    async def send_twink_info_to_forum(self, interaction, member_id, char_info, char_class, user_data):
        forum = interaction.guild.get_channel(FORUM_CHANNEL_ID)
        if not forum:
            return

        # Wir müssen den Thread finden. In deiner aktuellen Struktur haben wir keine thread_id.
        # Wir suchen daher nach einem Thread, der den Namen des Spielers oder die ID im Titel hat.
        # Besser: Wir suchen den Thread, den der Bot zuletzt für diesen User erstellt hat.
        
        target_thread = None
        real_name = user_data.get("real_name", "Unbekannt")
        
        # Suche in den aktiven Threads des Forums
        for thread in forum.threads:
            if str(member_id) in thread.name or real_name in thread.name:
                target_thread = thread
                break
        
        if not target_thread:
            # Falls kein Thread gefunden wurde, erstelle einen neuen (Fallbacksicherung)
            target_thread = await forum.create_thread(name=f"Eintrag: {real_name} | {member_id}", content="Initialer Post")

        # Hole die erste Nachricht im Thread (das Embed)
        async for message in target_thread.history(limit=1, oldest_first=True):
            if message.author == self.bot.user and message.embeds:
                old_embed = message.embeds[0]
                
                # Prüfen, ob das Twink-Feld schon existiert, sonst neu anlegen
                twink_list = []
                for field in old_embed.fields:
                    if field.name == "Twinks":
                        twink_list = [field.value]
                
                new_twink_entry = f"• **{char_info['name']}** ({char_class}) - [RIO]({f'https://raider.io/characters/eu/{char_info['realm']}/{char_info['name']}'})"
                
                # Falls das Feld "Twinks" noch nicht da ist, fügen wir es hinzu
                found = False
                new_fields = []
                for field in old_embed.fields:
                    if field.name == "Twinks":
                        new_fields.append(discord.EmbedField(name="Twinks", value=field.value + "\n" + new_twink_entry, inline=False))
                        found = True
                    else:
                        new_fields.append(field)
                
                if not found:
                    new_fields.append(discord.EmbedField(name="Twinks", value=new_twink_entry, inline=False))
                
                old_embed.fields = new_fields
                await message.edit(embed=old_embed)
                break

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