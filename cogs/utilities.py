import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from config import OFFIZIER_ROLLE_ID, LOG_CHANNEL_ID, ARCHIV_CHANNEL_ID, SERVER_ID

class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.archive_task.start()

    def cog_unload(self):
        self.archive_task.cancel()

    @tasks.loop(hours=6)
    async def archive_task(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(SERVER_ID)
        if not guild: return
        
        log_ch = guild.get_channel(LOG_CHANNEL_ID)
        arc_ch = guild.get_channel(ARCHIV_CHANNEL_ID)
        
        if log_ch and arc_ch:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
            async for msg in log_ch.history(limit=50):
                if msg.created_at < cutoff and "warcraftlogs.com" in msg.content:
                    await arc_ch.send(f"**Archivierter Log vom {msg.created_at.strftime('%d.%m.')}:**\n{msg.content}")
                    await msg.delete()

    @commands.command(name="raidumfrage")
    async def raidumfrage(self, ctx):
        if any(r.id == OFFIZIER_ROLLE_ID for r in ctx.author.roles):
            embed = discord.Embed(title="⚔️ Raid-Termine für die Woche", color=discord.Color.blue(), description="Bitte klickt auf die Tage, an denen ihr Zeit habt!")
            days = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]
            for d in days:
                embed.add_field(name=f"{d} (0)", value="Keine Stimmen", inline=False)
            await ctx.send(embed=embed, view=RaidPollView())

class RaidPollView(discord.ui.View):
    def __init__(self):
        # timeout=None ist wichtig, damit die View nicht abläuft!
        super().__init__(timeout=None)
        self.days = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction, day_idx):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_idx]
        voters = field.value.split(", ") if field.value != "Keine Stimmen" else []
        
        if interaction.user.mention in voters:
            voters.remove(interaction.user.mention)
        else:
            voters.append(interaction.user.mention)
        
        new_value = ", ".join(voters) if voters else "Keine Stimmen"
        embed.set_field_at(day_idx, name=f"{self.days[day_idx]} ({len(voters)})", value=new_value, inline=False)
        await interaction.response.edit_message(embed=embed)

    # Hier vergeben wir feste custom_ids für jeden Tag
    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="poll_do")
    async def b0(self, i, b): await self.handle_vote(i, 0)
    
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="poll_fr")
    async def b1(self, i, b): await self.handle_vote(i, 1)
    
    @discord.ui.button(label="Sa", style=discord.ButtonStyle.gray, custom_id="poll_sa")
    async def b2(self, i, b): await self.handle_vote(i, 2)
    
    @discord.ui.button(label="So", style=discord.ButtonStyle.gray, custom_id="poll_so")
    async def b3(self, i, b): await self.handle_vote(i, 3)
    
    @discord.ui.button(label="Mo", style=discord.ButtonStyle.gray, custom_id="poll_mo")
    async def b4(self, i, b): await self.handle_vote(i, 4)
    
    @discord.ui.button(label="Di", style=discord.ButtonStyle.gray, custom_id="poll_di")
    async def b5(self, i, b): await self.handle_vote(i, 5)
    
    @discord.ui.button(label="Mi", style=discord.ButtonStyle.gray, custom_id="poll_mi")
    async def b6(self, i, b): await self.handle_vote(i, 6)

async def setup(bot):
    await bot.add_cog(Utilities(bot))
