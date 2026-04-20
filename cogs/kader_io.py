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
        # Variablen aus Railway / Environment laden
        self.realm = os.getenv("REALM", "blackrock")
        self.guild_name = os.getenv("GUILD_NAME", "How to Interrupt")
        self.region = "eu"
        self.max_rank = int(os.getenv("MAX_KADER_RANK") or 10)
        
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        
        # Startet den Loop
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def get_detailed_role(self, spec, char_class):
        """Trennt Specs präzise in Tank, Heiler, Melee oder Ranged."""
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
        
        # Fallback basierend auf Klasse, falls Spec unbekannt
        return "Ranged" if char_class in ["Mage", "Warlock", "Hunter", "Priest"] else "Melee"

    async def get_stats_from_raiderio(self):
        """Holt die Gildenliste von Raider.io und verarbeitet die Rollen."""
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
                            # Filter nach Gilden-Rang
                            if m.get('rank', 10) > self.max_rank: continue
                            
                            char = m.get('character', {})
                            # Nur Max-Level Charaktere (Level 80 in TWW)
                            if char.get('level', 0) < 80: continue
                            
                            spec = char.get('active_spec_name')
                            rio_role = char.get('active_role') # TANK, HEALER, DPS
                            char_class = char.get('class')

                            if spec:
                                role = self.get_detailed_role(spec, char_class)
                                stats[role] += 1
                            elif rio_role:
                                # Fallback wenn Spec-Name von API nicht geliefert wird
                                if rio_role == "TANK": stats["Tank"] += 1
                                elif rio_role == "HEALER": stats["Heiler"] += 1
                                else:
                                    # Bei DPS: Grobe Zuordnung nach Klasse
                                    if char_class in ["Mage", "Warlock", "Hunter"]:
                                        stats["Ranged"] += 1
                                    else:
                                        stats["Melee"] += 1
                        return stats, None
                    return stats, f"API Fehler {resp.status}"
        except Exception as e:
            return stats, str(e)

    def create_embed(self, stats):
        """Erstellt das Embed mit den Fortschrittsbalken."""
        embed = discord.Embed(
            title="🛡️ Gilden-Kader Status",
            description=f"Kader-Auslastung für die Gilde **{self.guild_name}**",
            color=0x2b2d31
        )
        
        # Ziele und Labels (MID, HIGH, MAX, LOW)
        config = {
            "Tank":   {"goal": 2, "emoji": "🛡️", "label": "MID"},
            "Heiler": {"goal": 5, "emoji": "🌿", "label": "HIGH"},
            "Melee":  {"goal": 7, "emoji": "⚔️", "label": "MAX"},
            "Ranged": {"goal": 7, "emoji": "🏹", "label": "LOW"}
        }
        
        content = ""
        for role, data in config.items():
            count = stats[role]
            goal = data["goal"]
            
            # Balken generieren (z.B. ███░░)
            filled = min(count, goal)
            empty = max(0, goal - count)
            bar = "█" * filled + "░" * empty
            
            content += f"{data['emoji']} **{role.upper():<7}** → {bar} `{count}/{goal}` `{data['label']}`\n"
        
        embed.add_field(name="Kader Belegung", value=content, inline=False)
        embed.set_footer(text=f"Letztes Update: {datetime.now().strftime('%d.%m.%Y - %H:%M')} Uhr")
        return embed

    async def perform_update(self):
        """Führt das Update des bestehenden Posts aus."""
        if not self.recruitment_msg_id or not self.recruitment_channel_id:
            return
            
        try:
            channel = self.bot.get_channel(self.recruitment_channel_id) or await self.bot.fetch_channel(self.recruitment_channel_id)
            msg = await channel.fetch_message(self.recruitment_msg_id)
            stats, err = await self.get_stats_from_raiderio()
            if not err:
                await msg.edit(embed=self.create_embed(stats))
        except Exception as e:
            print(f"❌ KaderIO Update Fehler: {e}")

    @tasks.loop(hours=1) # Intervall auf 1 Stunde verkürzt für bessere Aktualität
    async def auto_update(self):
        await self.perform_update()

    @app_commands.command(name="kader_setup", description="Erstellt den initialen Kader-Post")
    async def kader_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats, err = await self.get_stats_from_raiderio()
        if err:
            return await interaction.followup.send(f"❌ Fehler beim Abrufen der Daten: {err}")
            
        msg = await interaction.channel.send(embed=self.create_embed(stats))
        await interaction.followup.send(
            f"✅ Post erstellt! Speichere diese ID in Railway unter `RECRUITMENT_MSG_ID`: `{msg.id}`"
        )

    @app_commands.command(name="kader_update", description="Aktualisiert den Kader-Post sofort")
    async def kader_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.perform_update()
        await interaction.followup.send("✅ Kader-Anzeige wurde manuell aktualisiert!")

# Diese Funktion muss ganz links am Rand stehen (keine Einrückung!)
async def setup(bot):
    await bot.add_cog(KaderIO(bot))