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
        # Railway Variablen laden
        self.realm = os.getenv("REALM")
        self.region = "eu"
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        self.kader_rolle_id = int(os.getenv("MITGLIED_ROLLE_ID") or 0) # Die Rolle, die gescannt wird
        
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def clean_name(self, name):
        """Bereinigt den Discord-Namen (entfernt Emojis/Zusätze wie 'Name | DD')"""
        # Nimmt nur das erste Wort und entfernt alles, was kein Buchstabe ist
        first_word = name.split()[0]
        return re.sub(r'[^a-zA-ZäöüÄÖÜß]', '', first_word)

    def get_role_from_spec(self, spec, char_class):
        """Ordnet Raider.io Daten einer Rolle zu."""
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker"]
        
        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        return "DPS"

    async def fetch_char_data(self, session, name):
        """Holt Daten von Raider.io."""
        clean_n = self.clean_name(name)
        url = f"https://raider.io/api/v1/characters/profile?region={self.region}&realm={self.realm}&name={clean_n}&fields=guild"
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    spec = data.get('active_spec_name')
                    char_class = data.get('class')
                    return self.get_role_from_spec(spec, char_class)
        except:
            return None

    async def get_stats_from_discord(self):
        """Scannt alle Discord-User mit der Kader-Rolle."""
        stats = {"Tank": 0, "Heiler": 0, "DPS": 0}
        
        # Sicherer Weg: Gilde über die ID aus der Config/Umgebungsvariable holen
        server_id = int(os.getenv("SERVER_ID") or 0)
        guild = self.bot.get_guild(server_id)
        
        if not guild:
            # Falls der Bot den Server noch nicht im Cache hat, versuchen wir ihn zu laden
            try:
                guild = await self.bot.fetch_guild(server_id)
            except:
                print(f"⚠️ Gilde mit ID {server_id} konnte nicht gefunden werden!")
                return stats
        
        role = guild.get_role(self.kader_rolle_id)
        if not role:
            print(f"⚠️ Rolle mit ID {self.kader_rolle_id} nicht gefunden!")
            return stats

        # Liste der Namen von allen, die die Rolle haben
        member_names = [m.display_name for m in role.members if not m.bot]
        
        if not member_names:
            print("ℹ️ Keine Mitglieder mit der angegebenen Rolle gefunden.")
            return stats

        async with aiohttp.ClientSession() as session:
            # Wir fragen Raider.io für alle Namen gleichzeitig ab
            tasks_list = [self.fetch_char_data(session, name) for name in member_names]
            results = await asyncio.gather(*tasks_list)
            
            for res in results:
                if res in stats:
                    stats[res] += 1
        return stats

    def create_embed(self, stats):
        """Erstellt das Embed mit der Balkengrafik."""
        embed = discord.Embed(
            title="🛡️ Aktueller Gilden-Kader",
            description="Diese Daten werden live von Raider.io abgefragt basierend auf euren Discord-Namen.",
            color=0x2b2d31
        )
        
        # Eure Ziel-Konfiguration (Wie viele braucht ihr?)
        # Diese Werte bestimmen, wie lang der Balken ist
        goals = {"Tank": 2, "Heiler": 5, "DPS": 14}
        emojis = {"Tank": "🛡️", "Heiler": "🌿", "DPS": "⚔️"}
        
        content = ""
        for role, count in stats.items():
            max_val = goals[role]
            # Balken-Logik
            filled = min(count, max_val)
            empty = max(0, max_val - filled)
            bar = "█" * filled + "░" * empty
            
            prio = "LOW" if count >= max_val else "HIGH"
            content += f"{emojis[role]} **{role.upper():<7}** {bar} `{count}/{max_val}`  `[{prio}]`\n"
        
        embed.add_field(name="Rekrutierungs-Status", value=content, inline=False)
        embed.set_footer(text=f"Letztes Update: {datetime.now().strftime('%d.%m. %H:%M')}")
        return embed

    @tasks.loop(hours=12)
    async def auto_update(self):
        """Automatisches Update alle 12 Stunden."""
        await self.perform_update()

    async def perform_update(self):
        """Die eigentliche Update-Logik für Forum/Nachricht."""
        if not self.recruitment_msg_id or not self.recruitment_channel_id:
            return

        try:
            channel = self.bot.get_channel(self.recruitment_channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(self.recruitment_channel_id)
            
            msg = await channel.fetch_message(self.recruitment_msg_id)
            stats = await self.get_stats_from_discord()
            await msg.edit(embed=self.create_embed(stats))
            print("✅ Kader-Post erfolgreich aktualisiert.")
        except Exception as e:
            print(f"❌ Fehler beim Kader-Update: {e}")

    @app_commands.command(name="kader_update", description="Aktualisiert den Kader-Post im Forum sofort")
    async def kader_update(self, interaction: discord.Interaction):
        """Manueller Start per Slash-Command."""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Keine Rechte!", ephemeral=True)

        await interaction.response.send_message("🔄 Scanne Raider.io Profile... bitte warten.", ephemeral=True)
        await self.perform_update()
        await interaction.edit_original_response(content="✅ Kader-Status wurde aktualisiert!")

async def setup(bot):
    await bot.add_cog(KaderIO(bot))