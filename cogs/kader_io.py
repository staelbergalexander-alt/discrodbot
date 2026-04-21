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

    def get_detailed_role(self, spec, char_class):
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker"]
        melees = ["Assassination", "Outlaw", "Subtlety", "Havoc", "Enhancement", "Feral", 
                  "Survival", "Arms", "Fury", "Retribution", "Frost", "Unholy", "Windwalker"]
        rangeds = ["Affliction", "Demonology", "Destruction", "Arcane", "Fire", "Frost", 
                   "Shadow", "Balance", "Marksmanship", "Beast Mastery", "Elemental", 
                   "Devastation", "Augmentation"]

        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        if spec in melees: return "Melee"
        if spec in rangeds: return "Ranged"
        return "Ranged" if char_class in ["Mage", "Warlock", "Hunter", "Priest"] else "Melee"

    async def get_stats_from_raiderio(self):
        stats = {"Tank": 0, "Heiler": 0, "Melee": 0, "Ranged": 0}
        members = []
        
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
                            char = m.get('character', {})
                            
                            # Filter: Nur Ränge bis max_rank berücksichtigen
                            if m.get('rank', 10) > self.max_rank: 
                                continue
                            
                            spec = char.get('active_spec_name')
                            rio_role = char.get('active_role') 
                            char_class = char.get('class')

                            if spec:
                                role = self.get_detailed_role(spec, char_class)
                                stats[role] += 1
                            elif rio_role:
                                if rio_role == "TANK": stats["Tank"] += 1
                                elif rio_role == "HEALER": stats["Heiler"] += 1
                                else:
                                    if char_class in ["Mage", "Warlock", "Hunter"]:
                                        stats["Ranged"] += 1
                                    else:
                                        stats["Melee"] += 1
                        
                        print(f"DEBUG: Kader berechnet -> {stats}")
                        return stats, None
                    return stats, f"API Fehler {resp.status}"
        except Exception as e:
            return stats, str(e)

def create_recruitment_text(self, stats):
        # Deine gewünschten Symbole
        filled_char = "▰"
        empty_char = "▱"
        total_blocks = 10

        def get_bar(role_name, goal):
            count = stats.get(role_name, 0)
            if goal > 0:
                ratio = count / goal
                filled = max(0, min(total_blocks, round(ratio * total_blocks)))
            else:
                filled = 0
            
            if count >= goal: status = "CLOSED"
            elif count >= (goal * 0.8): status = "LOW"
            elif count >= (goal * 0.5): status = "MID"
            else: status = "HIGH"
            
            return f"{filled_char * filled}{empty_char * (total_blocks - filled)} {status}"

        # Balken berechnen
        tank_bar   = get_bar("Tank", 2)
        heal_bar   = get_bar("Heiler", 5)
        melee_bar  = get_bar("Melee", 7)
        ranged_bar = get_bar("Ranged", 7)

        # Der Text mit allen Emojis aus deinem Bild
        full_text = (
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
            f"🛡️ **TANKS** ➜ {tank_bar}\n"
            f"🌿 **HEALER** ➜ {heal_bar}\n"
            f"⚔️ **MELEE DPS** ➜ {melee_bar}\n"
            f"🏹 **RANGED** ➜ {ranged_bar}\n\n"
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
        return full_text

    async def perform_update(self):
        if not self.recruitment_msg_id or not self.recruitment_channel_id:
            return
        try:
            channel = self.bot.get_channel(self.recruitment_channel_id) or await self.bot.fetch_channel(self.recruitment_channel_id)
            msg = await channel.fetch_message(self.recruitment_msg_id)
            stats, err = await self.get_stats_from_raiderio()
            
            if not err:
                # WICHTIG: Hier nutzen wir jetzt 'content=' statt 'embed='
                await msg.edit(content=self.create_recruitment_text(stats), embed=None)
        except Exception as e:
            print(f"❌ KaderIO Update Fehler: {e}")

    @tasks.loop(hours=1)
    async def auto_update(self):
        await self.perform_update()

    @app_commands.command(name="kader_setup", description="Erstellt den initialen Kader-Post")
    async def kader_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats, err = await self.get_stats_from_raiderio()
        if err:
            return await interaction.followup.send(f"❌ Fehler: {err}")
        msg = await interaction.channel.send(embed=self.create_embed(stats))
        await interaction.followup.send(f"✅ Post erstellt! ID für Railway `RECRUITMENT_MSG_ID`: `{msg.id}`")

    @app_commands.command(name="kader_update", description="Aktualisiert den Kader-Post sofort")
    async def kader_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.perform_update()
        await interaction.followup.send("✅ Kader-Anzeige wurde manuell aktualisiert!")

async def setup(bot):
    await bot.add_cog(KaderIO(bot))