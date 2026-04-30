import discord
from discord import app_commands, ui
from discord.ext import commands
import json
import os

# Datei für die Daten
DATA_FILE = "poll_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Die View, die die Buttons für die Antworten enthält
class DynamicPollView(discord.ui.View):
    def __init__(self, poll_id, options):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        
        # Erstellt für jede Antwortmöglichkeit einen eigenen Button
        for option in options:
            btn = discord.ui.Button(
                label=option.strip(),
                style=discord.ButtonStyle.secondary,
                custom_id=f"poll_{poll_id}_{option.strip()}"
            )
            btn.callback = self.vote_callback
            self.add_item(btn)

    async def vote_callback(self, interaction: discord.Interaction):
        data = load_data()
        poll = data.get(str(interaction.message.id))
        
        if not poll:
            return await interaction.response.send_message("Umfrage nicht gefunden.", ephemeral=True)

        user_id = str(interaction.user.id)
        chosen_option = interaction.data['custom_id'].split('_')[-1]
        
        # Stimmen des Users zählen
        user_votes = poll["voters"].get(user_id, [])
        
        if chosen_option in user_votes:
            return await interaction.response.send_message("Du hast bereits für diese Option gestimmt!", ephemeral=True)

        if len(user_votes) >= poll["max_per_person"]:
            return await interaction.response.send_message(f"Du darfst maximal {poll['max_per_person']} Stimmen abgeben!", ephemeral=True)

        # Stimme registrieren
        user_votes.append(chosen_option)
        poll["voters"][user_id] = user_votes
        poll["results"][chosen_option] = poll["results"].get(chosen_option, 0) + 1
        save_data(data)

        # Embed aktualisieren
        embed = interaction.message.embeds[0]
        new_desc = f"**{poll['question']}**\n\n"
        for opt, count in poll["results"].items():
            new_desc += f"**{opt}**: {count} Stimmen\n"
        
        new_desc += f"\n*Max. Stimmen pro Person: {poll['max_per_person']}*"
        embed.description = new_desc
        
        await interaction.response.edit_message(embed=embed)

# Das Fenster (Modal), das sich öffnet
class PollCreateModal(ui.Modal, title='Neue Umfrage erstellen'):
    frage = ui.TextInput(label='Deine Frage', placeholder='z.B. Was spielen wir heute?', min_length=5)
    optionen = ui.TextInput(label='Antworten (mit Komma trennen)', placeholder='z.B. LoL, WoW, CSGO', style=discord.TextStyle.paragraph)
    limit = ui.TextInput(label='Max. Stimmen pro Person', placeholder='z.B. 1', default='1', min_length=1, max_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        # Validierung des Limits
        try:
            max_votes = int(self.limit.value)
        except ValueError:
            return await interaction.response.send_message("Bitte gib eine gültige Zahl beim Limit an!", ephemeral=True)

        opts = self.optionen.value.split(',')
        embed = discord.Embed(title="📊 Umfrage", color=discord.Color.blue())
        
        desc = f"**{self.frage.value}**\n\n"
        results = {}
        for o in opts:
            o_clean = o.strip()
            desc += f"**{o_clean}**: 0 Stimmen\n"
            results[o_clean] = 0
            
        desc += f"\n*Max. Stimmen pro Person: {max_votes}*"
        embed.description = desc

        await interaction.response.send_message("Umfrage wird erstellt...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed)
        
        # View mit dynamischen Buttons hinzufügen
        view = DynamicPollView(str(msg.id), opts)
        await msg.edit(view=view)

        # In DB speichern
        data = load_data()
        data[str(msg.id)] = {
            "question": self.frage.value,
            "max_per_person": max_votes,
            "results": results,
            "voters": {}
        }
        save_data(data)

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="umfrage", description="Öffnet das Fenster für eine neue Umfrage")
    async def umfrage(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PollCreateModal())

async def setup(bot):
    await bot.add_cog(PollCog(bot))