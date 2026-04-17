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
            # --- ZEITRAUM BERECHNEN ---
            today = datetime.now()
            days_until_thursday = (3 - today.weekday()) % 7
            if days_until_thursday == 0 and today.hour > 12:
                days_until_thursday = 7
            
            start_date = today + timedelta(days=days_until_thursday)
            end_date = start_date + timedelta(days=6)
            zeitraum = f"{start_date.strftime('%d.%m.')} - {end_date.strftime('%d.%m.')}"

            # --- OPTIMIERTES EMBED ---
            embed = discord.Embed(
                title=f"⚔️ Raid-Planung ({zeitraum})",
                color=0x2b2d31, # Schickes dunkles Grau/Blau
                description="Klicke auf die Buttons unten, um dich für die Tage an- oder abzumelden."
            )
            
            days = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]
            for d in days:
                # Nutzt Emojis für bessere Scannbarkeit
                embed.add_field(name=f"📅 {d} (0)", value="---", inline=False)
            
            embed.set_footer(text="🔹 Blaues Icon = Angemeldet")
            await ctx.send(embed=embed, view=RaidPollView())

class RaidPollView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.days = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]

    async def handle_vote(self, interaction, day_idx):
        embed = interaction.message.embeds[0]
        field = embed.fields[day_idx]
        
        # Namen kompakt extrahieren und Emojis für die Logik entfernen
        current_value = field.value
        if current_value == "---":
            voters = []
        else:
            voters = [v.replace("🔹 ", "").strip() for v in current_value.split(" • ")]
        
        user_mention = interaction.user.mention
        
        if user_mention in voters:
            voters.remove(user_mention)
        else:
            voters.append(user_mention)
        
        # Neue Anzeige: "🔹 @Name • 🔹 @Name" statt untereinander
        if voters:
            new_value = " • ".join([f"🔹 {v}" for v in voters])
        else:
            new_value = "---"
            
        embed.set_field_at(
            day_idx, 
            name=f"📅 {self.days[day_idx]} ({len(voters)})", 
            value=new_value, 
            inline=False
        )
        await interaction.response.edit_message(embed=embed)

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
