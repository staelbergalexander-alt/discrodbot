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
        # Variablen aus Railway laden
        self.realm = os.getenv("REALM", "blackrock")
        self.guild_name = os.getenv("GUILD_NAME", "DeineGilde")
        self.region = "eu"
        self.min_rank = int(os.getenv("MAX_KADER_RANK") or 3)
        
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def get_detailed_role(self, spec, char_class):
        """Unterscheidet jetzt auch Melee und Ranged basierend auf Spec/Klasse."""
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker"]
        
        # Melee Specs
        melees = ["Assassination", "Outlaw", "Subtlety", "Havoc", "Enhancement", "Feral", 
                  "Survival", "Arms", "Fury", "Retribution", "Frost", "Unholy", "Windwalker"]

        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        if spec in melees: return "Melee"
        return "Ranged" # Alles andere (Mage, Hexer, Eule, etc.)

    async def get_stats_from_raiderio(self):
        """Holt Gildenmitglieder von Raider.io und filtert Mains (Rang & Level)."""
        stats = {"Tank": 0, "Heiler": 0, "Melee": 0, "Ranged": 0}
        
        safe_guild_name = urllib.parse.quote(self.guild_name)
        safe_realm = urllib.parse.quote(self.realm.lower().replace(" ", "-"))
        url = f"https://raider.io/api/v1/guilds/profile?region={self.region}&realm={safe_realm}&name={safe_guild_name}&fields=members"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('members', [])
                        
                        for m in members:
                            # Filter 1: Rang (Mains)
                            if m.get('rank', 10) > self.min_rank: continue
                            
                            char = m.get('character', {})
                            # Filter 2: Max Level
                            if char.get('level', 0) < 80: continue
                            
                            spec = char.get('active_spec_name')
                            if spec:
                                role = self.get_detailed_role(spec, char.get('class'))
                                stats[role] += 1
                        return stats, None
                    return stats, f"API Fehler {resp.status}"
        except Exception as e:
            return stats, str(e)

    def create_embed(self, stats):
        embed = discord.Embed(
            title="🛡️ Gilden-Kader Status",
            description=f"Aktualisiert via Raider.io für **{self.guild_name}**",
            color=0x2b2d31
        )
        
        # Ziele & Emojis passend zum Screenshot
        goals = {"Tank": 2, "Heiler": 5, "Melee": 7, "Ranged": 7}
        emojis = {"Tank": "🛡️", "Heiler": "🌿", "Melee": "⚔️", "Ranged": "🏹"}
        prio_labels = {"Tank": "MID", "Heiler": "HIGH", "Melee": "MAX", "Ranged": "LOW"}
        
        content = ""
        for role in ["Tank", "Heiler", "Melee", "Ranged"]:
            count = stats[role]
            max_v = goals[role]
            bar = "█" * min(count, max_v) + "░" * max(0, max_v - count)
            content += f"{emojis[role]} **{role.upper():<7}** → {bar} `{count}/{max_v}` `{prio_labels[role]}`\n"
        
        embed.add_field(name="Kader Belegung", value=content, inline=False)
        embed.set_footer(text=f"Letztes Update: {datetime.now().strftime('%H:%M')} Uhr")
        return embed

    async def perform_update(self):
        if not self.recruitment_msg_id: return
        try:
            channel = self.bot.get_channel(self.recruitment_channel_id) or await self.bot.fetch_channel(self.recruitment_channel_id)
            msg = await channel.fetch_message(self.recruitment_msg_id)
            stats, err = await self.get_stats_from_raiderio()
            if not err:
                await msg.edit(embed=self.create_embed(stats))
        except Exception as e:
            print(f"Update Fehler: {e}")

    @tasks.loop(hours=12)
    async def auto_update(self):
        await self.perform_update()

    @app_commands.command(name="kader_setup")
    async def kader_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats, err = await self.get_stats_from_raiderio()
        if err: return await interaction.followup.send(f"❌ {err}")
        
        msg = await interaction.channel.send(embed=self.create_embed(stats))
        await interaction.followup.send(f"✅ ID: `{msg.id}`")

    @app_commands.command(name="kader_update")
    async def kader_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.perform_update()
        await interaction.followup.send("✅ Aktualisiert!")

async def setup(bot):
    await bot.add_cog(KaderIO(bot))