import discord
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
from datetime import datetime

class LogsArchiver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Variablen aus Railway laden
        self.wcl_api_key = os.getenv("WCL_API_KEY")
        self.guild_name = os.getenv("GUILD_NAME") 
        self.realm = os.getenv("REALM")
        self.region = "EU"
        self.archive_channel_id = int(os.getenv("LOGS_CHANNEL_ID") or 0)
        
        self.last_log_id = None
        self.check_logs.start()

    def cog_unload(self):
        self.check_logs.cancel()

    @tasks.loop(minutes=15)
    async def check_logs(self):
        """Prüft alle 15 Minuten auf neue Gilden-Logs."""
        # Sicherheitscheck: Abbrechen, wenn Konfiguration fehlt
        if not self.wcl_api_key or not self.guild_name or not self.archive_channel_id:
            return
            
        await self.fetch_latest_logs()

    async def fetch_latest_logs(self):
        # Fix für Leerzeichen im Gilden-Namen für die URL
        safe_guild_name = self.guild_name.replace(" ", "%20")
        url = f"https://www.warcraftlogs.com:443/v1/reports/guild/{safe_guild_name}/{self.realm}/{self.region}?api_key={self.wcl_api_key}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        logs = await resp.json()
                        if not logs or not isinstance(logs, list): 
                            return
                        
                        latest_log = logs[0]
                        log_id = latest_log.get('id')

                        # LOGIK-ÄNDERUNG HIER:
                        # Wenn wir noch gar keine ID haben (erster Start), speichern wir die aktuelle 
                        # nur ab, ohne zu posten, um einen Spam-Flash beim Start zu vermeiden.
                        if self.last_log_id is None:
                            print(f"✅ Initialisierung: Speichere aktuellen Log {log_id} als Referenz.")
                            self.save_last_log_id(log_id)
                            return

                        # Wenn die ID sich unterscheidet, ist es ein wirklich neuer Log
                        if log_id != self.last_log_id:
                            print(f"🔔 Neuer Log gefunden: {log_id}")
                            await self.post_log(latest_log)
                            self.save_last_log_id(log_id) # Speichern für den nächsten Check/Neustart
                            
            except Exception as e:
                print(f"❌ LogsArchiver: Fehler beim Abruf: {e}")

    async def post_log(self, log_data):
        channel = self.bot.get_channel(self.archive_channel_id)
        if not channel: 
            return
        
        log_id = log_data['id']
        title = log_data.get('title', 'Neuer Raid Log')
        owner = log_data.get('owner', 'Unbekannt')
        # Zeitstempel von Millisekunden in lesbares Format
        start_time = datetime.fromtimestamp(log_data['start'] / 1000).strftime('%d.%m.%Y %H:%M')
        url = f"https://www.warcraftlogs.com/reports/{log_id}"
        
        embed = discord.Embed(
            title=f"📜 {title}",
            description=f"Ein neuer Raid-Log wurde auf Warcraftlogs gefunden.",
            color=discord.Color.purple(),
            url=url
        )
        embed.add_field(name="Erstellt von", value=owner, inline=True)
        embed.add_field(name="Startzeit", value=start_time, inline=True)
        embed.set_footer(text="Warcraft Logs Automatische Archivierung")
        
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LogsArchiver(bot))