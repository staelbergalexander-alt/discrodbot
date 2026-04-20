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
        # Variablen aus Railway
        self.realm = os.getenv("REALM") 
        self.guild_name = os.getenv("GUILD_NAME")
        self.region = "eu"
        
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def get_role_from_spec(self, spec, char_class):
        """Ordnet Specs den Rollen zu."""
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker"]
        
        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        return "DPS"
        
    def __init__(self, bot):
        # ... (deine bisherigen Variablen)
        self.min_rank = int(os.getenv("MAX_KADER_RANK") or 3) # Standard: Ränge 0, 1, 2, 3 werden gezählt

    async def get_stats_from_raiderio(self):
        """Liest die Gildenliste von Raider.io aus und filtert nach Rang & Level."""
        stats = {"Tank": 0, "Heiler": 0, "DPS": 0}
        
        import urllib.parse
        safe_guild_name = urllib.parse.quote(self.guild_name)
        safe_realm = urllib.parse.quote(self.realm.lower().replace(" ", "-"))

        url = f"https://raider.io/api/v1/guilds/profile?region={self.region}&realm={safe_realm}&name={safe_guild_name}&fields=members"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('members', [])
                        
                        count_filtered = 0
                        for m in members:
                            # FILTER 1: Gilden-Rang (z.B. nur Rang 0 bis 3)
                            # Raider.io Ränge: 0 = GM, 1 = Offi, etc.
                            char_rank = m.get('rank', 10)
                            if char_rank > self.min_rank:
                                continue
                                
                            char = m.get('character', {})
                            
                            # FILTER 2: Level (Nur Max-Level 80)
                            if char.get('level') < 80:
                                continue
                            
                            spec = char.get('active_spec_name')
                            char_class = char.get('class')
                            
                            if spec:
                                role = self.get_role_from_spec(spec, char_class)
                                stats[role] += 1
                                count_filtered += 1
                        
                        print(f"✅ KaderIO: {count_filtered} Mains nach Filter gefunden.")
                        return stats, None
                    else:
                        return stats, f"API Fehler {resp.status}"
        except Exception as e:
            return stats, str(e)

    def create_embed(self, stats):
        embed = discord.Embed(
            title="⚔️ Aktueller Gilden-Kader Status",
            description=f"Quelle: **Raider.io Gildenliste**\nRealm: `{self.realm.capitalize()}`",
            color=0x2b2d31
        )
        
        # Deine Ziele (Hier kannst du die Zahlen anpassen)
        goals = {"Tank": 2, "Heiler": 5, "DPS": 14}
        emojis = {"Tank": "🛡️", "Heiler": "🌿", "DPS": "⚔️"}
        
        content = ""
        for role, count in stats.items():
            max_val = goals[role]
            filled = min(count, max_val)
            bar = "█" * filled + "░" * max(0, max_val - filled)
            prio = "FULL" if count >= max_val else "OPEN"
            content += f"{emojis[role]} **{role.upper():<7}** {bar} `{count}/{max_val}` `[{prio}]`\n"
        
        embed.add_field(name="Kader Belegung", value=content, inline=False)
        embed.set_footer(text=f"Letzter API-Scan: {datetime.now().strftime('%H:%M')} Uhr")
        return embed

    @tasks.loop(hours=12)
    async def auto_update(self):
        if self.recruitment_msg_id > 0:
            await self.perform_update()

    async def perform_update(self):
        try:
            channel = self.bot.get_channel(self.recruitment_channel_id) or await self.bot.fetch_channel(self.recruitment_channel_id)
            msg = await channel.fetch_message(self.recruitment_msg_id)
            stats, err = await self.get_stats_from_raiderio()
            if not err:
                await msg.edit(embed=self.create_embed(stats))
        except Exception as e:
            print(f"❌ KaderIO Update Fehler: {e}")

    @app_commands.command(name="kader_setup", description="Initialisiert den Kader-Post")
    async def kader_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats, error = await self.get_stats_from_raiderio()
        if error:
            return await interaction.followup.send(f"❌ {error}")

        embed = self.create_embed(stats)
        msg = await interaction.channel.send(embed=embed)
        await interaction.followup.send(
            f"✅ Post erstellt!\nRECRUITMENT_MSG_ID: `{msg.id}`\nRECRUITMENT_CH_ID: `{interaction.channel_id}`"
        )

    @app_commands.command(name="kader_update", description="Aktualisiert den Kader-Status sofort")
    async def kader_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.perform_update()
        await interaction.followup.send("✅ Kader-Status wurde über Raider.io aktualisiert!")

async def setup(bot):
    await bot.add_cog(KaderIO(bot))