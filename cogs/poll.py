import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import os

DATA_FILE = "poll_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class DynamicPollView(discord.ui.View):
    def __init__(self, options):
        super().__init__(timeout=None)
        for option in options:
            self.add_item(PollButton(label=option.strip(), custom_id=f"vote_{option.strip()}"))

class PollButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        msg_id = str(interaction.message.id)
        
        if msg_id not in data:
            return await interaction.response.send_message("Umfrage-Daten nicht gefunden.", ephemeral=True)

        poll = data[msg_id]
        user_id = str(interaction.user.id)
        option = self.label

        # Liste aller Optionen, für die dieser User bereits gestimmt hat
        user_votes = [opt for opt, voters in poll["results"].items() if user_id in voters]

        # Logik: Stimme entfernen
        if user_id in poll["results"][option]:
            poll["results"][option].remove(user_id)
        else:
            # PRÜFUNG: Hat der User sein persönliches Limit erreicht?
            if len(user_votes) >= poll["votes_per_person"]:
                return await interaction.response.send_message(
                    f"Du hast bereits {poll['votes_per_person']} Stimme(n) abgegeben. Mehr sind nicht erlaubt!", 
                    ephemeral=True
                )
            
            poll["results"][option].append(user_id)

        save_data(data)

        # Embed aktualisieren
        embed = interaction.message.embeds[0]
        new_desc = f"**{poll['question']}**\n\n"
        
        for opt, voters in poll["results"].items():
            count = len(voters)
            # Balken-Optik (basiert hier zur Veranschaulichung auf 10er Schritten)
            bar = "🟦" * count if count <= 10 else "🟦" * 10 
            bar = bar.ljust(10, "⬛")
            
            new_desc += f"**{opt}**\n{bar} `{count} Stimmen`\n\n"

        new_desc += f"⚠️ *Limit: {poll['votes_per_person']} Stimme(n) pro Person*"
        embed.description = new_desc
        
        await interaction.response.edit_message(embed=embed)

class PollCreateModal(ui.Modal, title='Neue Umfrage erstellen'):
    frage = ui.TextInput(label='Frage', placeholder='Was möchtest du wissen?')
    optionen = ui.TextInput(
        label='Antworten (mit Komma trennen)', 
        placeholder='Option 1, Option 2, Option 3',
        style=discord.TextStyle.paragraph
    )
    limit_pro_person = ui.TextInput(label='Stimmen pro Person', default='1')

    async def on_submit(self, interaction: discord.Interaction):
        try:
            vpp = int(self.limit_pro_person.value)
        except ValueError:
            return await interaction.response.send_message("Das Limit muss eine Zahl sein!", ephemeral=True)

        opts = [o.strip() for o in self.optionen.value.split(',') if o.strip()]
        
        embed = discord.Embed(title="📊 Umfrage", color=0x5865F2)
        desc = f"**{self.frage.value}**\n\n"
        results = {o: [] for o in opts}
        
        for o in opts:
            desc += f"**{o}**\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛ `0 Stimmen`\n\n"
        
        desc += f"⚠️ *Limit: {vpp} Stimme(n) pro Person*"
        embed.description = desc

        await interaction.response.send_message("Umfrage wird erstellt...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=DynamicPollView(opts))

        data = load_data()
        data[str(msg.id)] = {
            "question": self.frage.value,
            "votes_per_person": vpp,
            "results": results
        }
        save_data(data)

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="umfrage", description="Umfrage mit Stimmen-Limit pro Person")
    async def umfrage(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PollCreateModal())

async def setup(bot):
    await bot.add_cog(PollCog(bot))