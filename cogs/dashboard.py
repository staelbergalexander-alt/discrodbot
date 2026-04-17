import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import aiohttp
import asyncio
from datetime import datetime

class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Jetzt aktualisieren 🔄", style=discord.ButtonStyle.primary, custom_id="dashboard_refresh_btn")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Dashboard")
        if cog:
            await interaction.response.send_message("🔄 Gear-Check läuft...", ephemeral=True)
            await cog.refresh_dashboard_logic()
        else:
            await interaction.response.send_message("❌ Fehler: Modul nicht gefunden.", ephemeral=True)

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "/app/data/mitglieder_db.json"
        self.config_path = "/app/data/dashboard_config.json"
        self.refresh_task.start()

    def cog_unload(self):
        self.refresh_task.cancel()

    async def fetch_gear(self, session, realm, name):
        url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get('gear', {}).get('items', {})
                    slots = ['chest', 'legs', 'boots', 'mainhand', 'offhand', 'finger1', 'finger2']
                    missing = any(info.get('enchant') is None for slot, info in items.items() if slot in slots)
                    return {
                        "ilvl": int(data.get('gear', {}).get('item_level_equipped', 0)),
                        "missing": missing,
                        "class": data.get('class', 'Unbekannt')
                    }
        except: return None
        return None

    @tasks.loop(minutes=30)
    async def refresh_task(self):
        await self.refresh_dashboard_logic()

    async def refresh_dashboard_logic(self):
        await self.bot.wait_until_ready()
        if not os.path.exists(self.config_path): return
        with open(self.config_path, "r") as f:
            config = json.load(f)
        
        channel = self.bot.get_channel(config['channel_id'])
        if not channel: return
        try: message = await channel.fetch_message(config['message_id'])
        except: return

        if not os.path.exists(self.db_path): return
        with open(self.db_path, "r") as f:
            db = json.load(f)

        # Listen für Kategorien
        tanks, heals, dps, not_ready = [], [], [], []

        async with aiohttp.ClientSession() as session:
            for uid, data in db.items():
                chars = data.get('chars', [])
                if not chars: continue
                
                # NUR den Main prüfen (Platz 1 in der Liste)
                main = chars[0]
                res = await self.fetch_gear(session, main['realm'], main['name'])
                
                if res:
                    member = channel.guild.get_member(int(uid))
                    display_name = member.display_name if member else main['name']
                    is_ready = res['ilvl'] >= 265 and not res['missing']
                    
                    # Formatierte Zeile mit Code-Block für das iLvl (sieht sauberer aus)
                    line = f"`{res['ilvl']}` **{display_name}** ({res['class']})"
                    
                    if is_ready:
                        cls = res['class'].lower()
                        # Rollenzuweisung
                        if cls in ['death knight', 'guardian druid', 'protection warrior', 'protection paladin', 'brewmaster monk', 'vengeance demon hunter']:
                            tanks.append(line)
                        elif cls in ['restoration druid', 'holy paladin', 'preservation evoker', 'mistweaver monk', 'holy priest', 'discipline priest', 'restoration shaman']:
                            heals.append(line)
                        else:
                            dps.append(line)
                    else:
                        reasons = []
                        if res['ilvl'] < 265: reasons.append("iLvl")
                        if res['missing']: reasons.append("VZ")
                        not_ready.append(f"⚠️ **{display_name}** *({', '.join(reasons)} fehlt)*")
                
                await asyncio.sleep(0.3)

        embed = discord.Embed(title="🛡️ RAID-READY DASHBOARD", color=0x2b2d31, timestamp=datetime.now())
        embed.description = "Anforderung: **iLvl 265+** & **Voll verzaubert**\n\n"
        
        if tanks:
            embed.add_field(name="🔹 TANKS", value="\n".join(tanks), inline=True)
        if heals:
            embed.add_field(name="💚 HEILER", value="\n".join(heals), inline=True)
        
        # Leeres Feld für Abstände bei 2 Spalten (Optional)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        if dps:
            embed.add_field(name="⚔️ SCHADENSAUSSTEILER", value="\n".join(dps), inline=False)
            
        if not_ready:
            embed.add_field(name="❌ NOCH IN ARBEIT", value="\n".join(not_ready), inline=False)

        embed.set_footer(text="Letztes Update")
        await message.edit(embed=embed, view=DashboardView())

    @app_commands.command(name="setup_dashboard", description="Erstellt das neue, smarte Dashboard")
    async def setup_dashboard(self, interaction: discord.Interaction):
        offizier_id = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
        if not any(r.id == offizier_id for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur für Offiziere!", ephemeral=True)

        await interaction.response.send_message("Dashboard wird erstellt...", ephemeral=True)
        embed = discord.Embed(title="⚔️ Dashboard", description="Lade Daten...")
        msg = await interaction.channel.send(embed=embed, view=DashboardView())
        
        with open(self.config_path, "w") as f:
            json.dump({"message_id": msg.id, "channel_id": interaction.channel_id}, f)
        
        await self.refresh_dashboard_logic()

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
