import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import aiohttp
import asyncio
from datetime import datetime

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "/app/data/mitglieder_db.json"
        self.config_path = "/app/data/dashboard_config.json"
        self.refresh_dashboard.start()

    def cog_unload(self):
        self.refresh_dashboard.cancel()

    async def fetch_gear(self, session, realm, name):
        url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get('gear', {}).get('items', {})
                    # Checkt wichtige Slots auf Verzauberungen
                    slots = ['chest', 'legs', 'boots', 'mainhand', 'offhand', 'finger1', 'finger2']
                    missing = any(info.get('enchant') is None for slot, info in items.items() if slot in slots)
                    return {
                        "ilvl": data.get('gear', {}).get('item_level_equipped', 0),
                        "missing": missing,
                        "class": data.get('class', 'Unbekannt')
                    }
        except: return None
        return None

    @tasks.loop(minutes=30)
    async def refresh_dashboard(self):
        await self.bot.wait_until_ready()
        if not os.path.exists(self.config_path): return
        
        with open(self.config_path, "r") as f:
            config = json.load(f)
        
        channel = self.bot.get_channel(config['channel_id'])
        if not channel: return
        try:
            message = await channel.fetch_message(config['message_id'])
        except: return

        if not os.path.exists(self.db_path): return
        with open(self.db_path, "r") as f:
            db = json.load(f)

        ready, working = [], []
        async with aiohttp.ClientSession() as session:
            for uid, data in db.items():
                for char in data.get('chars', []):
                    res = await self.fetch_gear(session, char['realm'], char['name'])
                    if res:
                        status = "✅" if res['ilvl'] >= 265 and not res['missing'] else "⚠️"
                        line = f"{status} **{char['name']}** ({res['class']}) - iLvl: {res['ilvl']}"
                        if status == "✅": ready.append(line)
                        else: working.append(f"{line} (Gear/VZ fehlt)")
                    await asyncio.sleep(0.2)

        embed = discord.Embed(title="⚔️ RAID-READY DASHBOARD", color=discord.Color.gold())
        embed.description = f"Letztes Update: <t:{int(datetime.now().timestamp())}:R>"
        embed.add_field(name="🟢 BEREIT", value="\n".join(ready)[:1024] or "Keiner", inline=False)
        embed.add_field(name="🔴 NOCH ARBEIT", value="\n".join(working)[:1024] or "Alle ready", inline=False)
        
        await message.edit(embed=embed)

    @app_commands.command(name="setup_dashboard")
    async def setup_dashboard(self, interaction: discord.Interaction):
        offizier_id = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
        if any(r.id == offizier_id for r in interaction.user.roles):
            embed = discord.Embed(title="Dashboard", description="Wird geladen...")
            await interaction.response.send_message("Dashboard wird erstellt...", ephemeral=True)
            msg = await interaction.channel.send(embed=embed)
            
            with open(self.config_path, "w") as f:
                json.dump({"message_id": msg.id, "channel_id": interaction.channel_id}, f)
            
            await self.refresh_dashboard()
        else:
            await interaction.response.send_message("Nur für Offiziere!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
