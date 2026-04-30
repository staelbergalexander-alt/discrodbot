import discord
from discord.ext import commands
from discord import app_commands
import json
import os

DATA_FILE = "poll_votes.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class LimitedPollView(discord.ui.View):
    def __init__(self):
        # WICHTIG: custom_id muss fest sein für setup_hook
        super().__init__(timeout=None)

    @discord.ui.button(label="Abstimmen", style=discord.ButtonStyle.green, custom_id="poll_vote_const")
    async def vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = load_data()
        msg_id = str(interaction.message.id)
        
        if msg_id not in data:
            return await interaction.response.send_message("Diese Umfrage ist nicht mehr aktiv.", ephemeral=True)

        poll = data[msg_id]
        user_id = interaction.user.id

        # 1. Schon abgestimmt?
        if user_id in poll["voters"]:
            return await interaction.response.send_message("Du hast bereits abgestimmt!", ephemeral=True)

        # 2. Limit erreicht?
        if len(poll["voters"]) >= poll["max"]:
            return await interaction.response.send_message("Leider sind schon alle Plätze belegt!", ephemeral=True)

        # 3. Stimme speichern
        poll["voters"].append(user_id)
        save_data(data)

        # Embed aktualisieren
        count = len(poll["voters"])
        limit = poll["max"]
        
        embed = interaction.message.embeds[0]
        embed.description = f"**{poll['question']}**\n\nStimmen: `{count}` / `{limit}`"

        if count >= limit:
            button.disabled = True
            button.label = "Vollbesetzt"
            button.style = discord.ButtonStyle.red
            embed.color = discord.Color.red()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed)

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="umfrage", description="Erstellt eine Umfrage mit Teilnehmerlimit")
    @app_commands.describe(frage="Was ist die Frage?", limit="Wie viele dürfen abstimmen?")
    async def umfrage(self, interaction: discord.Interaction, frage: str, limit: int):
        embed = discord.Embed(
            title="📊 Begrenzte Umfrage",
            description=f"**{frage}**\n\nStimmen: `0` / `{limit}`",
            color=discord.Color.blue()
        )
        
        # Wir schicken die Nachricht erst ab, um die ID zu bekommen
        await interaction.response.send_message(embed=embed, view=LimitedPollView())
        msg = await interaction.original_response()

        # Daten in JSON speichern
        data = load_data()
        data[str(msg.id)] = {
            "question": frage,
            "max": limit,
            "voters": []
        }
        save_data(data)

async def setup(bot):
    await bot.add_cog(PollCog(bot))