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

# Diese Klasse steuert die Buttons unter der Umfrage
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

        # Logik: Stimme abgeben oder zurückziehen (Toggle)
        if user_id in poll["results"][option]:
            poll["results"][option].remove(user_id)
        else:
            # Gesamtlimit prüfen
            current_total = sum(len(v) for v in poll["results"].values())
            if current_total >= poll["max_total"]:
                return await interaction.response.send_message(f"Limit von {poll['max_total']} Stimmen erreicht!", ephemeral=True)
            
            poll["results"][option].append(user_id)

        save_data(data)

        # Embed aktualisieren (Balken-Design)
        embed = interaction.message.embeds[0]
        new_desc = f"**{poll['question']}**\n\n"
        
        total_now = sum(len(v) for v in poll["results"].values())
        
        for opt, voters in poll["results"].items():
            count = len(voters)
            # Balken berechnen (10 Segmente)
            percent = (count / poll["max_total"]) if poll["max_total"] > 0 else 0
            filled = int(percent * 10)
            bar = "🟦" * filled + "⬛" * (10 - filled)
            
            new_desc += f"**{opt}**\n{bar} `{count} Stimmen`\n\n"

        new_desc += f"📊 **Gesamt: {total_now} / {poll['max_total']} Stimmen**"
        embed.description = new_desc
        
        await interaction.response.edit_message(embed=embed)

# Das Fenster (Modal), das sich öffnet
class PollCreateModal(ui.Modal, title='Neue Umfrage erstellen'):
    frage = ui.TextInput(label='Frage', placeholder='z.B. Welche Raidtage passen?', min_length=5)
    optionen = ui.TextInput(
        label='Antworten (mit Komma trennen)', 
        placeholder='Montag, Dienstag, Mittwoch', 
        style=discord.TextStyle.paragraph
    )
    limit = ui.TextInput(label='Gesamtlimit an Stimmen', placeholder='z.B. 44', default='44')

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_total = int(self.limit.value)
        except ValueError:
            return await interaction.response.send_message("Das Limit muss eine Zahl sein!", ephemeral=True)

        opts = [o.strip() for o in self.optionen.value.split(',') if o.strip()]
        if len(opts) < 2:
            return await interaction.response.send_message("Bitte gib mindestens 2 Optionen an!", ephemeral=True)

        # Initiales Embed erstellen
        embed = discord.Embed(title="📊 Limitierte Umfrage", color=0x5865F2)
        desc = f"**{self.frage.value}**\n\n"
        results = {}
        for o in opts:
            desc += f"**{o}**\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛ `0 Stimmen`\n\n"
            results[o] = []
        
        desc += f"📊 **Gesamt: 0 / {max_total} Stimmen**"
        embed.description = desc

        # Nachricht senden
        await interaction.response.send_message("Umfrage wird erstellt...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=DynamicPollView(opts))

        # Daten für Persistenz speichern
        data = load_data()
        data[str(msg.id)] = {
            "question": self.frage.value,
            "max_total": max_total,
            "results": results
        }
        save_data(data)

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="umfrage", description="Öffnet das Fenster für eine limitierte Umfrage")
    async def umfrage(self, interaction: discord.Interaction):
        # Das Fenster öffnen
        await interaction.response.send_modal(PollCreateModal())

async def setup(bot):
    await bot.add_cog(PollCog(bot))