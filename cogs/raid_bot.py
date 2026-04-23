import discord
from discord.ext import commands
import sqlite3

# Hilfsfunktion zum Speichern/Abrufen
def update_signup(user_id, name, wow_class):
    conn = sqlite3.connect('raid.db')
    c = conn.cursor()
    c.execute("REPLACE INTO signups (user_id, user_name, wow_class) VALUES (?, ?, ?)", 
              (user_id, name, wow_class))
    conn.commit()
    
    # Alle Anmeldungen für das Embed abrufen
    c.execute("SELECT user_name, wow_class FROM signups")
    rows = c.fetchall()
    conn.close()
    return rows

class ClassSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Krieger", emoji="🛡️"),
            discord.SelectOption(label="Magier", emoji="🔥"),
            discord.SelectOption(label="Priester", emoji="✨"),
            discord.SelectOption(label="Hexenmeister", emoji="💜"),
            discord.SelectOption(label="Druide", emoji="🍃"),
            discord.SelectOption(label="Paladin", emoji="🔨"),
            # Füge hier weitere Klassen hinzu...
        ]
        super().__init__(placeholder="Wähle deine Klasse...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # 3. & 4. Daten in DB speichern und Liste abrufen
        all_signups = update_signup(interaction.user.id, interaction.user.display_name, self.values[0])
        
        # Embed aktualisieren
        new_embed = interaction.message.embeds[0]
        signup_list = "\n".join([f"{name} ({w_class})" for name, w_class in all_signups])
        
        if not signup_list:
            signup_list = "Noch keine Anmeldungen."
            
        # Wir überschreiben das Feld "Teilnehmer" im Embed
        new_embed.clear_fields()
        new_embed.add_field(name="Teilnehmer", value=signup_list, inline=False)
        
        await interaction.response.edit_message(embed=new_embed)

class RaidView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClassSelect())

    @discord.ui.button(label="Abmelden", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect('raid.db')
        conn.execute("DELETE FROM signups WHERE user_id = ?", (interaction.user.id,))
        conn.commit()
        conn.close()
        
        # Liste nach dem Löschen neu laden
        await self.callback_update(interaction)

    async def callback_update(self, interaction):
        # Hilfsfunktion zum Refreshen des Embeds nach Abmeldung
        conn = sqlite3.connect('raid.db')
        c = conn.cursor()
        c.execute("SELECT user_name, wow_class FROM signups")
        rows = c.fetchall()
        conn.close()
        
        new_embed = interaction.message.embeds[0]
        new_embed.clear_fields()
        signup_list = "\n".join([f"{n} ({c})" for n, c in rows]) or "Noch keine Anmeldungen."
        new_embed.add_field(name="Teilnehmer", value=signup_list, inline=False)
        await interaction.response.edit_message(embed=new_embed)

@bot.command()
async def raid_setup(ctx):
    embed = discord.Embed(
        title="⚔️ Raid Anmeldung",
        description="Bitte wähle unten deine Klasse aus, um dich für den nächsten Raid anzumelden!",
        color=discord.Color.blue()
    )
    embed.add_field(name="Teilnehmer", value="Noch keine Anmeldungen.", inline=False)
    await ctx.send(embed=embed, view=RaidView())