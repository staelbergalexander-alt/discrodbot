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
        # Variablen aus Railway laden
        self.realm = os.getenv("REALM")
        self.region = "eu"
        self.server_id = int(os.getenv("SERVER_ID") or 0)
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        self.kader_rolle_id = int(os.getenv("MITGLIED_ROLLE_ID") or 0)
        
        # Startet den automatischen 12-Stunden-Loop
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def clean_name(self, name):
        """Extrahiert den Char-Namen (entfernt Emojis, Rollen-Tags etc.)"""
        # Trenne bei Sonderzeichen wie |, -, / oder Leerzeichen und nimm das erste Wort
        first_word = re.split(r'[ \||/|-]', name)[0]
        # Entferne alles, was kein Buchstabe ist
        return re.sub(r'[^a-zA-ZäöüÄÖÜß]', '', first_word)

    def get_role_from_spec(self, spec, char_class):
        """Ordnet Raider.io Specs den Rollen zu."""
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker"]
        
        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        return "DPS"

    async def fetch_char_data(self, session, name):
        """Fragt Raider.io für einen einzelnen Namen ab."""
        clean_n = self.clean_name(name)
        if not clean_n: return None
        
        url = f"https://raider.io/api/v1/characters/profile?region={self.region}&realm={self.realm}&name={clean_n}"
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    spec = data.get('active_spec_name')
                    if not spec: return None
                    return self.get_role_from_spec(spec, data.get('class'))
                return None
        except:
            return None

    async def get_stats_from_discord(self):
        """Sammelt alle Mitglieder der Rolle und holt deren IO-Daten."""
        stats = {"Tank": 0, "Heiler": 0, "DPS": 0}
        
        guild = self.bot.get_guild(self.server_id)
        if not guild:
            try:
                guild = await self.bot.fetch_guild(self.server_id)
            except:
                print(f"❌ KaderIO: Server {self.server_id} nicht gefunden.")
                return stats
        
        role = guild.get_role(self.kader_rolle_id)
        if not role:
            print(f"❌ KaderIO: Rolle {self.kader_rolle_id} nicht gefunden.")
            return stats

        # Namen aller Mitglieder mit dieser Rolle (keine Bots)
        member_names = [m.display_name for m in role.members if not m.bot]
        
        if not member_names:
            return stats

        async with aiohttp.ClientSession() as session:
            tasks_list = [self.fetch_char_data(session, name) for name in member_names]
            results = await asyncio.gather(*tasks_list)
            
            for res in results:
                if res in stats:
                    stats[res] += 1
        return stats

    def create_embed(self, stats):
        """Erzeugt das Embed im Balken-Design."""
        embed = discord.Embed(
            title="⚔️ Aktueller Gilden-Kader Status",
            description="Die Zahlen basieren auf den aktuellen Raider.io Profilen eurer Discord-Mitglieder.",
            color=0x2b2d31
        )
        
        # Deine gewünschte Kader-Größe
        goals = {"Tank": 2, "Heiler": 5, "DPS": 14}
        emojis = {"Tank": "🛡️", "Heiler": "🌿", "DPS": "⚔️"}
        
        content = ""
        for role, count in stats.items():
            max_val = goals[role]
            filled = min(count, max_val)
            empty = max(0, max_val - filled)
            bar = "█" * filled + "░" * empty
            
            # Priorität anzeigen
            prio = "FULL" if count >= max_val else "OPEN"
            content += f"{emojis[role]} **{role.upper():<7}** {bar} `{count}/{max_val}`  `[{prio}]`\n"
        
        embed.add_field(name="Rekrutierung", value=content, inline=False)
        embed.set_footer(text=f"Letzter Scan: {datetime.now().strftime('%d.%m. %H:%M')} Uhr")
        return embed

    @tasks.loop(hours=12)
    async def auto_update(self):
        """Automatisches Update alle 12 Stunden."""
        await self.perform_update()

    async def perform_update(self):
        """Logik zum Aktualisieren der Nachricht mit Fehlerschutz."""
        # 1. Check: Sind die IDs überhaupt gesetzt?
        if self.recruitment_msg_id <= 0 or self.recruitment_channel_id <= 0:
            print("ℹ️ KaderIO: Warte auf Setup. IDs sind noch auf 0.")
            return

        try:
            channel = self.bot.get_channel(self.recruitment_channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(self.recruitment_channel_id)
            
            # 2. Check: Existiert die Nachricht?
            try:
                msg = await channel.fetch_message(self.recruitment_msg_id)
            except discord.NotFound:
                print(f"⚠️ KaderIO: Nachricht {self.recruitment_msg_id} nicht gefunden. Bitte /kader_setup nutzen.")
                return

            # 3. Stats holen und Nachricht bearbeiten
            stats = await self.get_stats_from_discord()
            await msg.edit(embed=self.create_embed(stats))
            print("✅ Kader-Post erfolgreich aktualisiert.")
            
        except Exception as e:
            # Verhindert, dass der Bot bei Fehlern komplett stoppt
            print(f"❌ Fehler beim Kader-Update: {e}")
            
    @app_commands.command(name="kader_update", description="Erzwingt ein sofortiges Update des Kader-Status")
    async def kader_update(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Nur für Admins!", ephemeral=True)

        await interaction.response.send_message("🔄 Scanne Raider.io Profile...", ephemeral=True)
        await self.perform_update()
        await interaction.edit_original_response(content="✅ Kader-Status wurde aktualisiert!")

    @app_commands.command(name="kader_setup", description="Erstellt die Nachricht, die der Bot zukünftig verwaltet")
    async def kader_setup(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Nur für Admins!", ephemeral=True)
            
        await interaction.response.send_message("Erstelle initiale Nachricht...", ephemeral=True)
        stats = await self.get_stats_from_discord()
        embed = self.create_embed(stats)
        
        # Bot sendet neue Nachricht
        msg = await interaction.channel.send(embed=embed)
        
        await interaction.edit_original_response(
            content=f"✅ Nachricht erstellt!\nKopiere diese ID in Railway als `RECRUITMENT_MSG_ID`: `{msg.id}`\nDie Channel ID ist: `{interaction.channel_id}`"
        )

async def setup(bot):
    await bot.add_cog(KaderIO(bot))