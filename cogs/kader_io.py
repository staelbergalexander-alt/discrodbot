import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
import re
from datetime import datetime

class KaderIO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Variablen laden
        self.realm = os.getenv("REALM")
        self.region = "eu"
        self.server_id = int(os.getenv("SERVER_ID") or 0)
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        self.kader_rolle_id = int(os.getenv("MITGLIED_ROLLE_ID") or 0)
        
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def clean_name(self, name):
        first_word = re.split(r'[ \||/|-]', name)[0]
        return re.sub(r'[^a-zA-ZäöüÄÖÜß]', '', first_word)

    def get_role_from_spec(self, spec, char_class):
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker"]
        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        return "DPS"

    async def fetch_char_data(self, session, name):
        clean_n = self.clean_name(name)
        if not clean_n: return None
        url = f"https://raider.io/api/v1/characters/profile?region={self.region}&realm={self.realm}&name={clean_n}"
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self.get_role_from_spec(data.get('active_spec_name'), data.get('class'))
        except:
            return None

    async def get_stats_from_discord(self):
        stats = {"Tank": 0, "Heiler": 0, "DPS": 0}
        guild = self.bot.get_guild(self.server_id)
        if not guild:
            guild = await self.bot.fetch_guild(self.server_id)
        
        role = guild.get_role(self.kader_rolle_id)
        if not role:
            return stats, "Rolle nicht gefunden"

        member_names = [m.display_name for m in role.members if not m.bot]
        if not member_names:
            return stats, "Keine Mitglieder in der Rolle"

        async with aiohttp.ClientSession() as session:
            tasks_list = [self.fetch_char_data(session, name) for name in member_names]
            results = await asyncio.gather(*tasks_list)
            for res in results:
                if res in stats: stats[res] += 1
        return stats, None

    def create_embed(self, stats):
        embed = discord.Embed(title="⚔️ Gilden-Kader Status", color=0x2b2d31)
        goals = {"Tank": 2, "Heiler": 5, "DPS": 14}
        emojis = {"Tank": "🛡️", "Heiler": "🌿", "DPS": "⚔️"}
        content = ""
        for role, count in stats.items():
            max_val = goals[role]
            bar = "█" * min(count, max_val) + "░" * max(0, max_val - count)
            prio = "FULL" if count >= max_val else "OPEN"
            content += f"{emojis[role]} **{role.upper():<7}** {bar} `{count}/{max_val}` `[{prio}]`\n"
        embed.description = content
        embed.set_footer(text=f"Update: {datetime.now().strftime('%H:%M')} Uhr")
        return embed

    @tasks.loop(hours=12)
    async def auto_update(self):
        if self.recruitment_msg_id > 0:
            await self.perform_update()

    async def perform_update(self):
        try:
            channel = self.bot.get_channel(self.recruitment_channel_id) or await self.bot.fetch_channel(self.recruitment_channel_id)
            msg = await channel.fetch_message(self.recruitment_msg_id)
            stats, err = await self.get_stats_from_discord()
            await msg.edit(embed=self.create_embed(stats))
        except:
            pass

    @app_commands.command(name="kader_setup", description="Initialisiert den Kader-Post")
    async def kader_setup(self, interaction: discord.Interaction):
        # 1. Sofort antworten, damit Discord nicht denkt, der Bot sei tot
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 2. Stats holen
            stats, error = await self.get_stats_from_discord()
            if error:
                return await interaction.followup.send(f"❌ Fehler: {error}. Prüfe die MITGLIED_ROLLE_ID!")

            # 3. Embed senden
            embed = self.create_embed(stats)
            msg = await interaction.channel.send(embed=embed)
            
            # 4. Erfolgsmeldung mit IDs
            await interaction.followup.send(
                f"✅ Post erstellt!\n\n**IDs für Railway:**\n"
                f"RECRUITMENT_MSG_ID: `{msg.id}`\n"
                f"RECRUITMENT_CH_ID: `{interaction.channel_id}`"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Kritischer Fehler: {e}")

    @app_commands.command(name="kader_update", description="Sofort-Update")
    async def kader_update(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.perform_update()
        await interaction.followup.send("✅ Update durchgeführt!")

async def setup(bot):
    await bot.add_cog(KaderIO(bot))