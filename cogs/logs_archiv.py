import discord
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
from datetime import datetime

class LogsArchiver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Variablen aus Railway laden [cite: 1]
        self.wcl_api_key = os.getenv("WCL_API_KEY")
        self.guild_name = os.getenv("How to Interrupt")
        self.realm = os.getenv("REALM")
        self.region = "EU"
        self.archive_channel_id = int(os.getenv("LOGS_CHANNEL_ID") or 0)
        
        self.last_log_id = None
        self.check_logs.start()

    def cog_unload(self):
        self.check_logs.cancel()

    @tasks.loop(minutes=15)
    async def check_logs(self):
        # Sicherheitscheck: Nur ausführen, wenn alle Daten da sind
        if not self.wcl_api_key or not self.guild_name or not self.realm:
            print("⚠️ LogsArchiver: Fehlende Konfiguration (API Key, Gilde oder Realm).")
            return
        await self.fetch_latest_logs()

    async def fetch_latest_logs(self):
        # Fix für Leerzeichen im Gilden-Namen
        safe_guild_name = self.guild_name.replace(" ", "%20")
        url = f"https://www.warcraftlogs.com:443/v1/reports/guild/{safe_guild_name}/{self.realm}/{self.region}?api_key={self.wcl_api_key}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200: [cite: 5]
                        logs = await resp.json()
                        if not logs: return
                        
                        latest_log = logs[0] [cite: 6]
                        log_id = latest_log.get('id')
                        
                        if self.last_log_id is not None and log_id != self.last_log_id: [cite: 7]
                            await self.post_log(latest_log)
                        
                        self.last_log_id = log_id [cite: 8]
            except Exception as e:
                print(f"❌ Fehler beim Log-Abruf: {e}")

    async def post_log(self, log_data):
        channel = self.bot.get_channel(self.archive_channel_id)
        if not channel: return
        
        log_id = log_data['id'] [cite: 9]
        title = log_data.get('title', 'Neuer Raid Log')
        owner = log_data.get('owner', 'Unbekannt')
        start_time = datetime.fromtimestamp(log_data['start'] / 1000).strftime('%d.%m.%Y %H:%M')
        url = f"https://www.warcraftlogs.com/reports/{log_id}"
        
        embed = discord.Embed(
            title=f"📜 {title}",
            description=f"Ein neuer Raid-Log wurde hochgeladen.",
            color=discord.Color.purple(), [cite: 10]
            url=url
        )
        embed.add_field(name="Erstellt von", value=owner, inline=True)
        embed.add_field(name="Datum", value=start_time, inline=True)
        embed.set_footer(text="Warcraft Logs Archiv")
        
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LogsArchiver(bot))