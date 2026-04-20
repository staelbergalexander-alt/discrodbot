import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import os
import asyncio
from datetime import datetime

class KaderIO(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Variablen aus Railway
        self.realm = os.getenv("REALM") # z.B. "blackhand"
        self.guild_name = os.getenv("GUILD_NAME") # Euer Gildenname (Leerzeichen = %20)
        self.region = "eu"
        
        self.recruitment_msg_id = int(os.getenv("RECRUITMENT_MSG_ID") or 0)
        self.recruitment_channel_id = int(os.getenv("RECRUITMENT_CH_ID") or 0)
        
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    def get_role_from_spec(self, spec, char_class):
        """Ordnet Specs den Rollen zu."""
        tanks = ["Blood", "Guardian", "Brewmaster", "Protection", "Vengeance"]
        healers = ["Restoration", "Holy", "Mistweaver", "Preservation", "Discipline", "Prevoker", "Mistweaver"]
        
        if spec in tanks: return "Tank"
        if spec in healers: return "Heiler"
        return "DPS"

    async def get_stats_from_raiderio(self):
        """Liest die gesamte Gildenliste von Raider.io aus."""
        stats = {"Tank": 0, "Heiler": 0, "DPS": 0}
        
        # URL für Gilden-Profile (Mitglieder-Feld)
        # Beispiel: https://raider.io/api/v1/guilds/profile?region=eu&realm=blackhand&name=Gildenname&fields=members
        url = f"https://raider.io/api/v1/guilds/profile?region={self.region}&realm={self.realm}&name={self.guild_name}&fields=members"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('members', [])
                        
                        print(f"🔍 KaderIO: Scanne {len(members)} Gildenmitglieder von Raider.io...")
                        
                        for m in members:
                            char = m.get('character', {})
                            # Wir nehmen nur Chars über einem gewissen Level oder Rang, falls gewünscht
                            # Hier zählen wir einfach alle, die einen aktiven Spec haben
                            spec = char.get('active_spec_name')
                            char_class = char.get('class')
                            
                            if spec:
                                role = self.get_role_from_spec(spec, char_class)
                                stats[role] += 1
                        
                        return stats, None
                    else:
                        return stats, f"API Fehler: {resp.status}"
        except Exception as e:
            return stats, str(e)

    def create_embed(self, stats):
        embed = discord.Embed(
            title="⚔️ Aktueller Gilden-Kader Status",
            description=f"Quelle: **Raider.io Gildenliste**\nRealm: `{self.realm.capitalize()}`",
            color=0x2b2d31
        )
        
        # Deine Ziele (Anpassbar)
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
                print("✅ Kader-Post via Raider.io aktualisiert.")
        except Exception as e:
            print(f"❌ Fehler beim Auto-Update: {e}")

    @app_commands.command(name="kader_setup", description="Initialisiert den Kader-Post")
    async def kader_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        stats, error = await self.get_stats_from_raiderio()
        if error:
            return await interaction.followup.send(f"❌ Fehler beim Abrufen der Gilde: {error}")

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