"""import discord
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
from datetime import datetime

class LogsArchiver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # WCL v2 nutzt Client ID & Secret
        self.client_id = os.getenv("WCL_CLIENT_ID")
        self.client_secret = os.getenv("WCL_CLIENT_SECRET")
        self.guild_id = os.getenv("WCL_GUILD_ID") # v2 braucht oft die numerische ID
        self.archive_channel_id = int(os.getenv("LOGS_CHANNEL_ID") or 0)
        
        self.token = None
        self.db_file = "last_log.txt"
        self.last_log_id = self.load_last_log_id()
        
        self.check_logs.start()

    def load_last_log_id(self):
        if os.path.exists(self.db_file):
            with open(self.db_file, "r") as f:
                return f.read().strip()
        return None

    # DIESE FUNKTION HAT GEFEHLT ODER WAR FALSCH BENANNT:
    def save_last_log_id(self, log_id):
        with open(self.db_file, "w") as f:
            f.write(str(log_id))
        self.last_log_id = log_id

    async def get_access_token(self):
        """"""Holt den OAuth2 Token für v2 API.""""""
        url = "https://www.warcraftlogs.com/oauth/token"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, 
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(self.client_id, self.client_secret)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data['access_token']
                else:
                    print("❌ WCL: Token Fehler")

    @tasks.loop(minutes=15)
    async def check_logs(self):
        if not self.client_id or not self.archive_channel_id:
            return
        
        # Token erneuern falls nötig
        if not self.token:
            await self.get_access_token()
            
        await self.fetch_latest_logs_v2()

    async def fetch_latest_logs_v2(self):
        url = "https://www.warcraftlogs.com/api/v2/client"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        # GraphQL Query für den neusten Log
        query = """"""
        query($guildId: Int) {
          reportData {
            reports(guildID: $guildId, limit: 1) {
              data {
                code
                title
                startTime
                owner { name }
                zone { name }
              }
            }
          }
        }
        """"""
        variables = {"guildId": int(self.guild_id)}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={'query': query, 'variables': variables}, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    reports = result.get('data', {}).get('reportData', {}).get('reports', {}).get('data', [])
                    
                    if not reports:
                        return
                    
                    latest = reports[0]
                    log_id = latest['code']

                    if self.last_log_id is None:
                        self.save_last_log_id(log_id)
                        print(f"✅ Initialisiert mit Log: {log_id}")
                        return

                    if log_id != self.last_log_id:
                        await self.post_log_v2(latest)
                        self.save_last_log_id(log_id)
                elif resp.status == 401: # Token abgelaufen
                    self.token = None

    async def post_log_v2(self, log_data):
        channel = self.bot.get_channel(self.archive_channel_id)
        if not channel: return

        log_id = log_data['code']
        title = log_data['title']
        zone = log_data['zone']['name'] if log_data['zone'] else "Unbekannt"
        owner = log_data['owner']['name']
        url = f"https://www.warcraftlogs.com/reports/{log_id}"

        embed = discord.Embed(
            title=f"📜 {title}",
            description=f"Neuer Raid-Log in **{zone}** archiviert.",
            color=discord.Color.purple(),
            url=url,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Erstellt von", value=owner, inline=True)
        embed.set_footer(text=f"WCL v2 Archiv | ID: {log_id}")
        
        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LogsArchiver(bot))"""