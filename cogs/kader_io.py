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
        # Variablen aus Railway laden - WICHTIG: Hier wurden die Fehler behoben
        self.realm = os.getenv("REALM", "blackrock")
        self.guild_name = os.getenv("GUILD_NAME", "How to Interrupt")
        self.region = "eu"
        self.max_rank = int(os.getenv("MAX_KADER_RANK") or 10)
        
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        
        # Startet den Loop erst, wenn die IDs vorhanden sind
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def get_detailed_role(self, spec, char_class):
        """Trennt Specs präzise in Tank, Heiler, Melee oder Ranged."""
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker"]
        
        melees = ["Assassination", "Outlaw", "Subtlety", "Havoc", "Enhancement", "Feral", 
                  "Survival", "Arms", "Fury", "Retribution", "Frost", "Unholy", "Windwalker"]

        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        if spec in melees: return "Melee"
        return "Ranged"

    async def get_stats_from_raiderio(self):
        """Holt die Gildenliste von Raider.io."""
        stats = {"Tank": 0, "Heiler": 0, "Melee": 0, "Ranged": 0}
        
        # URL-Sicherheit
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
                            if m.get('rank', 10) > self.max_rank: continue
                            char = m.get('character', {})
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
        """Design exakt nach deinem Wunsch-Screenshot."""
        embed = discord.Embed(
            title="🛡️ Gilden-Kader Status",
            description=f"Aktualisiert via Raider.io für **{self.guild_name}**",
            color=0x2b2d31
        )
        
        # Definition der Ziele und Status-Labels
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
            bar = "█" * min(count, goal) + "░" * max(0, goal - count)
            content += f"{data['emoji']} **{role.upper():<7}** → {bar} `{count}/{goal}` `{data['label']}`\n"
        
        embed.add_field(name="Kader Belegung", value=content, inline=False)
        embed.set_footer(text=f"Letztes Update: {datetime.now().strftime('%H:%M')} Uhr")
        return embed

    async def perform_update(self):
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

    @tasks.loop(hours=12)
    async def auto_update(self):
        await self.perform_update()

    @app_commands.command(name="kader_setup", description="Erstellt den Kader-Post")
    async def kader_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats, err = await self.get_stats_from_raiderio()
        if err:
            return await interaction.followup.send(f"❌ Fehler: {err}")
            
        msg = await interaction.channel.send(embed=self.create_embed(stats))
        await interaction.followup.send(
            f"✅ Post erstellt! ID für Railway `RECRUITMENT_MSG_ID`: `{msg.id}`"
        )

    @app_commands.command(name="kader_update", description="Sofort-Update")
    async def kader_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.perform_update()
        await interaction.followup.send("✅ Kader wurde aktualisiert!")

async def setup(bot):
    await bot.add_cog(KaderIO(bot))