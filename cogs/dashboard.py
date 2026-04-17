import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import aiohttp
import asyncio
from datetime import datetime

class DashboardView(discord.ui.View):
    """View für den permanenten Refresh-Button unter dem Dashboard."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Jetzt aktualisieren 🔄", style=discord.ButtonStyle.primary, custom_id="dashboard_refresh_btn")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Wir suchen das Dashboard-Cog, um die Logik auszuführen
        cog = interaction.client.get_cog("Dashboard")
        if cog:
            # Sofortige Antwort, damit Discord keinen Timeout wirft
            await interaction.response.send_message("🔄 Gear-Check gestartet... Bitte warten.", ephemeral=True)
            await cog.refresh_dashboard_logic()
        else:
            await interaction.response.send_message("❌ Fehler: Dashboard-Modul nicht gefunden.", ephemeral=True)

class Dashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "/app/data/mitglieder_db.json"
        self.config_path = "/app/data/dashboard_config.json"
        self.refresh_task.start()

    def cog_unload(self):
        self.refresh_task.cancel()

    async def fetch_gear(self, session, realm, name):
        """Holt Gear-Daten von der Raider.io API."""
        url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={realm}&name={name}&fields=gear"
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get('gear', {}).get('items', {})
                    # Relevante Slots für Verzauberungen
                    slots = ['chest', 'legs', 'boots', 'mainhand', 'offhand', 'finger1', 'finger2']
                    missing = any(info.get('enchant') is None for slot, info in items.items() if slot in slots)
                    return {
                        "ilvl": data.get('gear', {}).get('item_level_equipped', 0),
                        "missing": missing,
                        "class": data.get('class', 'Unbekannt')
                    }
        except:
            return None
        return None

    @tasks.loop(minutes=30)
    async def refresh_task(self):
        """Automatischer Hintergrund-Update alle 30 Minuten."""
        await self.refresh_dashboard_logic()

    async def refresh_dashboard_logic(self):
        """Die Kernlogik zum Scannen der Datenbank und Editieren des Embeds."""
        await self.bot.wait_until_ready()
        
        if not os.path.exists(self.config_path): return
        with open(self.config_path, "r") as f:
            config = json.load(f)
        
        channel = self.bot.get_channel(config['channel_id'])
        if not channel: return
        
        try:
            message = await channel.fetch_message(config['message_id'])
        except:
            return

        if not os.path.exists(self.db_path): return
        with open(self.db_path, "r") as f:
            db = json.load(f)

        ready_list, working_list = [], []
        
       # ... (vorheriger Code im Dashboard Cog)
        async with aiohttp.ClientSession() as session:
            for uid, data in db.items():
                chars = data.get('chars', [])
                if not chars:
                    continue

                # SMART: Wir nehmen NUR den ersten Charakter (den Main)
                main_char = chars[0]
                
                res = await self.fetch_gear(session, main_char['realm'], main_char['name'])
                if res:
                    is_ready = res['ilvl'] >= 265 and not res['missing']
                    status = "✅" if is_ready else "⚠️"
                    
                    # Wir holen den Discord-Namen für das Dashboard
                    member = channel.guild.get_member(int(uid))
                    display_name = member.display_name if member else main_char['name']
                    
                    line = f"{status} **{display_name}** ({res['class']}) - iLvl: {res['ilvl']}"
                    
                    if is_ready:
                        ready_list.append(line)
                    else:
                        reasons = []
                        if res['ilvl'] < 265: reasons.append("iLvl niedrig")
                        if res['missing']: reasons.append("VZ fehlt")
                        working_list.append(f"{line} *({', '.join(reasons)})*")
                
                await asyncio.sleep(0.3)
        # ... (restlicher Code zum Senden des Embeds)

        embed = discord.Embed(
            title="⚔️ RAID-READY DASHBOARD", 
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.description = f"Letztes Update: <t:{int(datetime.now().timestamp())}:R>\n\n*Anforderung: iLvl 265+ & alle VZ vorhanden.*"
        
        # Felder befüllen (Limitierung auf 1024 Zeichen beachten)
        ready_text = "\n".join(ready_list)[:1024] or "Keine Charaktere bereit."
        working_text = "\n".join(working_list)[:1024] or "Alle Charaktere sind bereit!"
        
        embed.add_field(name="🟢 BEREIT", value=ready_text, inline=False)
        embed.add_field(name="🔴 NOCH ARBEIT", value=working_text, inline=False)
        embed.set_footer(text="Nutze den Button für ein manuelles Update")

        # Nachricht mit der View (Button) aktualisieren
        await message.edit(embed=embed, view=DashboardView())

    @app_commands.command(name="setup_dashboard", description="Erstellt ein neues Dashboard mit Refresh-Button")
    async def setup_dashboard(self, interaction: discord.Interaction):
        offizier_id = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
        if not any(r.id == offizier_id for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Nur für Offiziere!", ephemeral=True)

        await interaction.response.send_message("Dashboard wird initialisiert...", ephemeral=True)
        
        embed = discord.Embed(title="⚔️ Dashboard", description="Lade Daten von Raider.io...")
        # Die View wird hier beim ersten Senden direkt angehängt
        msg = await interaction.channel.send(embed=embed, view=DashboardView())
        
        with open(self.config_path, "w") as f:
            json.dump({"message_id": msg.id, "channel_id": interaction.channel_id}, f)
        
        # Ersten Scan sofort starten
        await self.refresh_dashboard_logic()

async def setup(bot):
    await bot.add_cog(Dashboard(bot))
