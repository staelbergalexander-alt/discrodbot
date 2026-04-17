import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from config import OFFIZIER_ROLLE_ID, LOG_CHANNEL_ID, ARCHIV_CHANNEL_ID, SERVER_ID

class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.archive_task.start()

    @tasks.loop(hours=6)
    async def archive_task(self):
        guild = self.bot.get_guild(SERVER_ID)
        if not guild: return
        log_ch = guild.get_channel(LOG_CHANNEL_ID)
        arc_ch = guild.get_channel(ARCHIV_CHANNEL_ID)
        
        if log_ch and arc_ch:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
            async for msg in log_ch.history(limit=50):
                if msg.created_at < cutoff and "warcraftlogs.com" in msg.content:
                    await arc_ch.send(f"**Archiv:** {msg.content}")
                    await msg.delete()

    @commands.command()
    async def raidumfrage(self, ctx):
        if any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
            embed = discord.Embed(title="⚔️ Raid-Umfrage", color=discord.Color.blue())
            days = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]
            for d in days:
                embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
            await ctx.send(embed=embed, view=RaidPollView())

class RaidPollView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    async def handle_vote(self, interaction, day_idx):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_idx]
        voters = field.value.split(", ") if field.value != "Keine Stimmen" else []
        if interaction.user.mention in voters: voters.remove(interaction.user.mention)
        else: voters.append(interaction.user.mention)
        
        day_name = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"][day_idx]
        embed.set_field_at(day_idx, name=f"{day_name} ({len(voters)})", value=", ".join(voters) if voters else "Keine Stimmen", inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray)
    async def do(self, i, b): await self.handle_vote(i, 0)
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray)
    async def fr(self, i, b): await self.handle_vote(i, 1)
    # ... (Die restlichen Buttons analog hinzufügen)

async def setup(bot):
    await bot.add_cog(Utilities(bot))
