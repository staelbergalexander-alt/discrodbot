import discord
from discord.ext import commands
from discord import app_commands, Poll

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="umfrage", description="Erstellt eine native Discord-Umfrage")
    async def umfrage(self, interaction: discord.Interaction):
        # Wir nutzen wieder ein Modal, um die Daten abzufragen
        await interaction.response.send_modal(NativePollModal())

class NativePollModal(discord.ui.Modal, title='Neue Umfrage erstellen'):
    frage = discord.ui.TextInput(label='Deine Frage', placeholder='z.B. Mögliche Raidtage', min_length=5)
    optionen = discord.ui.TextInput(
        label='Antworten (pro Zeile eine)', 
        placeholder='Montag\nDienstag\nMittwoch', 
        style=discord.TextStyle.paragraph
    )
    max_antworten = discord.ui.TextInput(label='Wie viele Antworten darf man wählen?', default='1')

    async def on_submit(self, interaction: discord.Interaction):
        # Optionen in eine Liste umwandeln
        opts_list = self.optionen.value.split('\n')
        opts_list = [o.strip() for o in opts_list if o.strip()][:10] # Discord erlaubt max 10

        try:
            limit = int(self.max_antworten.value)
        except ValueError:
            limit = 1

        # Erstellen der nativen Poll
        # multiple=True erlaubt das Aussehen aus deinem Screenshot
        poll = Poll(
            question=self.frage.value,
            duration=datetime.timedelta(hours=24), # Dauer der Umfrage
            multiple=True if limit > 1 else False
        )

        # Antworten hinzufügen
        for opt in opts_list:
            poll.add_answer(text=opt)

        await interaction.response.send_message(poll=poll)

async def setup(bot):
    await bot.add_cog(PollCog(bot))