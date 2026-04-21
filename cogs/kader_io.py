import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
import pytz
import urllib.parse
from datetime import datetime

class KaderIO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.realm = os.getenv("REALM", "blackrock")
        self.guild_name = os.getenv("GUILD_NAME", "How to Interrupt")
        self.region = "eu"
        self.max_rank = int(os.getenv("MAX_KADER_RANK") or 4)
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    async def get_stats_from_raiderio(self):
        stats = {"Tank": 0, "Heiler": 0, "Melee": 0, "Ranged": 0}
        safe_name = urllib.parse.quote(self.guild_name)
        safe_realm = urllib.parse.quote(self.realm.lower().replace(" ", "-"))
        url = f"https://raider.io/api/v1/guilds/profile?region={self.region}&realm={safe_realm}&name={safe_name}&fields=members"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('members', [])
                        for m in members:
                            if m.get('rank', 10) <= self.max_rank:
                                char = m.get('character', {})
                                role = char.get('active_role')
                                spec = char.get('active_spec_name')
                                char_class = char.get('class')
                                
                                if role == "TANK": stats["Tank"] += 1
                                elif role == "HEALER": stats["Heiler"] += 1
                                elif char_class in ["Mage", "Warlock", "Hunter", "Priest"] and spec not in ["Discipline", "Holy"]:
                                    stats["Ranged"] += 1
                                else:
                                    stats["Melee"] += 1
                        return stats, None
                    return stats, f"API Fehler {resp.status}"
        except Exception as e:
            return stats, str(e)

    def create_recruitment_text(self, stats):
        # Symbole
        f_c, e_c = "▰", "▱"
        total_blocks = 10

        def b(role_name, goal, manual_count=None):
            # Wenn manual_count gesetzt ist, ignorieren wir Raider.io für diese Rolle
            count = manual_count if manual_count is not None else stats.get(role_name, 0)
            
            percent = (count / goal) if goal > 0 else 0
            filled = max(0, min(total_blocks, round(percent * total_blocks)))
            
            if count >= goal: 
                s = "CLOSED"
            elif count >= (goal * 0.8): 
                s = "LOW"
            elif count >= (goal * 0.5): 
                s = "MID"
            else: 
                s = "HIGH"
            
            return f"{f_c * filled}{e_c * (total_blocks - filled)} {s}"

        # --- HIER MANUELLE KORREKTUR EINTRAGEN ---
        # Wenn Raider.io die Tanks nicht findet, schreiben wir hier '2' rein:
        tank_bar   = b("Tank", 2, manual_count=2) # 2 von 2 -> Immer CLOSED
        
        # Die anderen lassen wir auf Automatik (stats.get)
        heal_bar   = b("Heiler", 5, manual_count=2) 
        melee_bar  = b("Melee", 7, manual_count=5)  
        ranged_bar = b("Ranged", 7, manual_count=4)
        
        tz = pytz.timezone('Europe/Berlin')
        berlin_now = datetime.now(tz)
        time_str = berlin_now.strftime('%d.%m.%Y - %H:%M')

        # Der finale Text (Exakt wie dein Screenshot)
        return (
            "🔥 **Raid & Mythic+ Gilde sucht Verstärkung!** 🔥\n\n"
            "**Wer wir sind:**\n"
            "Wir sind eine entspannte, aber ambitionierte Gilde mit Fokus auf Raid- und Mythic+ Content. "
            "Unser Ziel ist es, gemeinsam Progress zu machen, starke Keys zu pushen und dabei eine angenehme, "
            "stressfreie Atmosphäre zu bewahren.\n\n"
            "✨ **Was wir bieten:**\n"
            "Regelmäßige Raids (HC / optional Mythic Progress)\n"
            "Spontane Mythic+ Gruppen für kontinuierlichen Fortschritt\n"
            "Strukturierte Organisation & erfahrene Spieler\n\n"
            "📌 **WAS DU MITBRINGST:**\n"
            "Ambitionierte Spieler für Raid & Mythic+ (Midcore)\n"
            "Zuverlässigkeit, Lernbereitschaft & Teamgeist\n\n"
            "**UNSERE AKTUELLE KLASSEN-PRIO:**\n"
            "Unsere M+ Gruppen und der Raidkader wachsen stetig – deshalb suchen wir wieder aktiv nach Verstärkung!\n\n"
            f"🛡️ **TANKS** ➜ {tank_bar}\n"
            f"🌿 **HEALER** ➜ {heal_bar}\n"
            f"⚔️ **MELEE** ➜ {melee_bar}\n"
            f"🏹 **RANGED** ➜ {ranged_bar}\n\n"
            "🤝 **Was wir erreichen wollen:**\n"
            "Mehrere feste interne M+ Stammgruppen etablieren\n"
            "Aktuellen Raid (NHC & HC) clearen – aktuell 4/9 HC\n\n"
            "🕒 **Zeiten:**\n"
            "Aktuell flexibel – Termine werden spontan angekündigt\n "
            "**Mythic+:**\n Täglich, je nach Verfügbarkeit in spontanen Gruppen\n\n"
            "📩 **Interesse?**\n"
            "https://discord.gg/Kv3kpraqGk\n\n"
            "**Battle.net:** Boom#2893\n\n"
            f"*Zuletzt aktualisiert: {time_str} Uhr*"
        )

    async def perform_update(self):
        if not self.recruitment_msg_id or not self.recruitment_channel_id:
            return
        try:
            channel = self.bot.get_channel(self.recruitment_channel_id) or await self.bot.fetch_channel(self.recruitment_channel_id)
            msg = await channel.fetch_message(self.recruitment_msg_id)
            stats, err = await self.get_stats_from_raiderio()
            
            if not err:
                # Wir editieren die Nachricht und ENTFERNEN das Embed (embed=None)
                # Der gesamte Inhalt steht nun in 'content'
                await msg.edit(content=self.create_recruitment_text(stats), embed=None)
                print("✅ Rekrutierungstext erfolgreich aktualisiert.")
        except Exception as e:
            print(f"❌ Update Error: {e}")

    @tasks.loop(hours=1)
    async def auto_update(self):
        await self.perform_update()

    @app_commands.command(name="kader_update")
    async def kader_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.perform_update()
        await interaction.followup.send("✅ Aktualisiert!")

async def setup(bot):
    await bot.add_cog(KaderIO(bot))