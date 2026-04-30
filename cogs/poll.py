import discord
from discord.ext import commands
from discord import app_commands
import json
import os

DATA_FILE = "poll_data.json"

class DynamicPollView(discord.ui.View):
    def __init__(self, msg_id, options, max_total_votes):
        super().__init__(timeout=None)
        self.msg_id = str(msg_id)
        self.max_total_votes = max_total_votes
        
        for option in options:
            self.add_item(PollButton(label=option, custom_id=f"p_{msg_id}_{option}"))

class PollButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        
        poll = data.get(str(interaction.message.id))
        if not poll: return

        user_id = str(interaction.user.id)
        
        # Prüfung: Gesamtlimit erreicht?
        total_votes = sum(len(v) for v in poll["results"].values())
        if total_votes >= poll["max_total"] and user_id not in [u for sub in poll["results"].values() for u in sub]:
            return await interaction.response.send_message("Das Stimmen-Limit für diese Umfrage wurde erreicht!", ephemeral=True)

        # Stimme verarbeiten (Umschalten: an/aus)
        option = self.label
        if user_id in poll["results"][option]:
            poll["results"][option].remove(user_id)
        else:
            poll["results"][option].append(user_id)

        with open(DATA_FILE, "w") as f:
            json.dump(data, f)

        # Embed aktualisieren (Balken-Optik simulieren)
        embed = interaction.message.embeds[0]
        new_desc = ""
        current_total = sum(len(v) for v in poll["results"].values())
        
        for opt, voters in poll["results"].items():
            count = len(voters)
            # Simulierter Balken
            bar = "🟦" * count + "⬜" * (poll["max_total"] - count)
            new_desc += f"**{opt}**\n{count} Stimmen\n\n"

        embed.description = f"{poll['question']}\n\n{new_desc}\nGesamt: {current_total}/{poll['max_total']}"
        await interaction.response.edit_message(embed=embed)

class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="limitpoll", description="Umfrage mit hartem Stimmen-Limit")
    async def limitpoll(self, interaction: discord.Interaction, frage: str, optionen: str, limit: int):
        opts = [o.strip() for o in optionen.split(",")]
        
        embed = discord.Embed(title="📊 Limitierte Umfrage", color=0x5865F2)
        desc = f"{frage}\n\n"
        results = {}
        for o in opts:
            desc += f"**{o}**\n0 Stimmen\n\n"
            results[o] = []
        
        embed.description = f"{desc}Gesamt: 0/{limit}"
        
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        
        # Daten speichern
        if not os.path.exists(DATA_FILE): data = {}
        else:
            with open(DATA_FILE, "r") as f: data = json.load(f)
            
        data[str(msg.id)] = {"question": frage, "results": results, "max_total": limit}
        with open(DATA_FILE, "w") as f: json.dump(data, f)
        
        await msg.edit(view=DynamicPollView(msg.id, opts, limit))

async def setup(bot):
    await bot.add_cog(PollCog(bot))