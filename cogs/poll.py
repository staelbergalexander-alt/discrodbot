import discord
from discord.ext import commands
from discord import app_commands
import datetime

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="umfrage", description="Erstellt eine native Umfrage (wie im Screenshot)")
    async def umfrage(self, interaction: discord.Interaction):
        # Öffnet das Eingabefenster
        await interaction.response.send_modal(NativePollModal())

class NativePollModal(discord.ui.Modal, title='Neue Umfrage erstellen'):
    frage = discord.ui.TextInput(label='Frage', placeholder='z.B. Welche Tage passen euch?', min_length=2)
    optionen = discord.ui.TextInput(
        label='Antworten (Eine pro Zeile)', 
        placeholder='Montag\nDienstag\nMittwoch', 
        style=discord.TextStyle.paragraph
    )
    dauer = discord.ui.TextInput(label='Dauer in Stunden', default='24')
    mehrfach = discord.ui.TextInput(label='Mehrfachwahl? (ja/nein)', default='ja')

    async def on_submit(self, interaction: discord.Interaction):
        # Antworten verarbeiten
        opts = [o.strip() for o in self.optionen.value.split('\n') if o.strip()]
        if len(opts) < 2:
            return await interaction.response.send_message("Bitte gib mindestens 2 Optionen an!", ephemeral=True)
        
        # Einstellungen
        is_multiple = self.mehrfach.value.lower() in ['ja', 'yes', 'true', '1']
        try:
            hours = int(self.dauer.value)
        except:
            hours = 24

        # Native Discord Poll erstellen
        poll = discord.Poll(
            question=self.frage.value,
            duration=datetime.timedelta(hours=hours),
            multiple=is_multiple
        )

        for opt in opts[:10]: # Discord erlaubt max. 10 Optionen
            poll.add_answer(text=opt)

        await interaction.response.send_message(poll=poll)

async def setup(bot):
    await bot.add_cog(PollCog(bot))