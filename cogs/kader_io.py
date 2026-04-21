import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
import urllib.parse
from datetime import datetime

class KaderIO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.realm = os.getenv("REALM", "blackrock")
        self.guild_name = os.getenv("GUILD_NAME", "How to Interrupt")
        self.region = "eu"
        self.max_rank = int(os.getenv("MAX_KADER_RANK") or 10)
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
        f_c, e_c = "▰", "▱"
        def b(n, g):
            c = stats.get(n, 0)
            p = max(0, min(10, round((c/g)*10))) if g > 0 else 0
            s = "CLOSED" if c >= g else ("LOW" if c >= g*0.8 else "HIGH")
            return f"{f_c*p}{e_c*(10-p)} {s}"

        t_b, h_b = b("Tank", 2), b("Heiler", 5)
        m_b, r_b = b("Melee", 7), b("Ranged", 7)

        return (
            "🔥 **Raid & Mythic+ Gilde sucht Verstärkung!** 🔥\n\n"
            "**Wer wir sind:**\n"
            "Wir sind eine entspannte, aber ambitionierte Gilde mit Fokus auf Raid- und Mythic+ Content. Unser Ziel ist es, gemeinsam Progress zu machen, starke Keys zu pushen und dabei eine angenehme, stressfreie Atmosphäre zu bewahren. Bei uns steht Teamplay im Vordergrund – ohne Drama, dafür mit Motivation.\n\n"
            "✨ **Was wir bieten:**\n"
            "Regelmäßige Raids (HC / optional Mythic Progress)\n"
            "Spontane Mythic+ Gruppen für kontinuierlichen Fortschritt\n"
            "Strukturierte Organisation & erfahrene Spieler\n"
            "Ruhige, erwachsene Community\n"
            "Unterstützung bei Gear, Logs und persönlicher Verbesserung\n\n"
            "📌 **WAS DU MITBRINGST:**\n"
            "Ambitionierte Spieler für Raid & Mythic+ (Midcore)\n"
            "Raid-Bereitschaft (Vorbereitung, Taktiken, Consumables)\n"
            "Sicherer Umgang mit Mechanics (Interrupts, CC, Movement)\n"
            "Zuverlässigkeit, Lernbereitschaft & Teamgeist\n\n"
            "**UNSERE AKTUELLE KLASSEN-PRIO:**\n"
            "Unsere M+ Gruppen und der Raidkader wachsen stetig – deshalb suchen wir wieder aktiv nach Verstärkung!\n\n"
            f"🛡️ **TANKS** ➜ {t_b}\n"
            f"🌿 **HEALER** ➜ {h_b}\n"
            f"⚔️ **MELEE DPS** ➜ {m_b}\n"
            f"🏹 **RANGED** ➜ {r_b}\n\n"
            "🤝 **Was wir erreichen wollen:**\n"
            "Mehrere feste interne M+ Stammgruppen etablieren\n"
            "Aktuellen Raid (NHC & HC) clearen – aktuell 4/9 HC, danach Mythic Trys\n"
            "Ein kollegiales Umfeld: RL geht vor. Ehrgeiz ja – toxisches Verhalten nein\n\n"
            "🕒 **Zeiten:**\n"
            "**Raids:**\n"
            "Aktuell flexibel – Termine werden spontan angekündigt\n"
            "**Mythic+:**\n"
            "Täglich, je nach Verfügbarkeit in spontanen Gruppen\n\n"
            "📩 **Interesse?**\n"
            "https://discord.gg/Kv3kpraqGk\n\n"
            "**Battle.net:**\n"
            "Boom#2893\n\n"
            f"*Zuletzt aktualisiert: {datetime.now().strftime('%d.%m.%Y - %H:%M')} Uhr*"
        )

    async def perform_update(self):
        if not self.recruitment_msg_id: return
        try:
            ch = self.bot.get_channel(self.recruitment_channel_id) or await self.bot.fetch_channel(self.recruitment_channel_id)
            msg = await ch.fetch_message(self.recruitment_msg_id)
            stats, err = await self.get_stats_from_raiderio()
            if not err:
                await msg.edit(content=self.create_recruitment_text(stats))
        except Exception as e: print(f"Update Error: {e}")

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