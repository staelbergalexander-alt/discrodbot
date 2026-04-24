import discord
from discord.ext import commands
from discord import ui
import sqlite3

# --- KONFIGURATION ---
RAID_CATEGORY_ID = int(os.getenv('RAID_CATEGORY_ID') or 0)
CLASS_ORDER = [
    "Krieger", "Paladin", "Todesritter", "Jäger", "Schamane", 
    "Druide", "Schurke", "Mönch", "Dämonenjäger", "Rufer", 
    "Magier", "Hexenmeister", "Priester"
]

def update_db_signup(channel_id, user_id, name, wow_class):
    conn = sqlite3.connect('raid.db')
    c = conn.cursor()
    # Tabelle erstellen falls nicht existent
    c.execute('''CREATE TABLE IF NOT EXISTS signups 
                 (channel_id INTEGER, user_id INTEGER, user_name TEXT, wow_class TEXT, 
                 PRIMARY KEY (channel_id, user_id))''')
    
    if wow_class is None: # Löschen
        c.execute("DELETE FROM signups WHERE channel_id = ? AND user_id = ?", (channel_id, user_id))
    else: # Speichern
        c.execute("REPLACE INTO signups (channel_id, user_id, user_name, wow_class) VALUES (?, ?, ?, ?)", 
                  (channel_id, user_id, name, wow_class))
    
    conn.commit()
    c.execute("SELECT user_name, wow_class FROM signups WHERE channel_id = ?", (channel_id,))
    rows = c.fetchall()
    conn.close()
    
    # Sortieren nach CLASS_ORDER
    rows.sort(key=lambda x: CLASS_ORDER.index(x[1]) if x[1] in CLASS_ORDER else 99)
    return rows

class ClassSelect(ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=c, emoji=self.get_emoji(c)) for c in CLASS_ORDER]
        super().__init__(placeholder="Wähle deine Klasse...", options=options, custom_id="raid_bot:class_select")

    def get_emoji(self, cls):
        emojis = {"Krieger": "<:wowwarrior:1493404491045797918>", 
                  "Paladin": "<:wowpaladin:1493404654434783232>", 
                  "Todesritter": "<:wowdeathknight:1493404419512074331>", 
                  "Jäger": "<:wowhunter:1493404509945462906>", 
                  "Schamane": "<:wowshaman:1493404277748797470>",                  
                  "Druide": "<:wowdruid:1493404330420604999>", 
                  "Schurke": "<:wowrogue:1493404583534268517>", 
                  "Mönch": "<:wowmonk:1493404364281217165>", 
                  "Dämonenjäger": "<:wowdemonhunter:1493404389065359390>", 
                  "Rufer": "<:evokerroundpng:1497024873011351672>", 
                  "Magier": "<:wowmage:1493404551968063519>", 
                  "Hexenmeister": "<:wowwarlock:1493404636370046996> ", 
                  "Priester": "<:wowpriest:1493404618141470801> "}
        return emojis.get(cls, "❓")

    async def callback(self, interaction: discord.Interaction):
        all_signups = update_db_signup(interaction.channel_id, interaction.user.id, interaction.user.display_name, self.values[0])
        await self.refresh_message(interaction, all_signups)

    async def refresh_message(self, interaction, all_signups):
        embed = interaction.message.embeds[0]
        signup_text = "\n".join([f"**{w_class}**: {name}" for name, w_class in all_signups]) or "Noch keine Anmeldungen."
        embed.set_field_at(0, name=f"Teilnehmer ({len(all_signups)})", value=signup_text, inline=False)
        await interaction.response.edit_message(embed=embed)

class RaidView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClassSelect())

    @ui.button(label="Abmelden", style=discord.ButtonStyle.red, custom_id="raid_bot:leave")
    async def leave(self, interaction: discord.Interaction, button: ui.Button):
        all_signups = update_db_signup(interaction.channel_id, interaction.user.id, interaction.user.display_name, None)
        embed = interaction.message.embeds[0]
        signup_text = "\n".join([f"**{w_class}**: {name}" for name, w_class in all_signups]) or "Noch keine Anmeldungen."
        embed.set_field_at(0, name=f"Teilnehmer ({len(all_signups)})", value=signup_text, inline=False)
        await interaction.response.edit_message(embed=embed)

class RaidDetailModal(ui.Modal, title='Neuen Raid planen'):
    raid_name = ui.TextInput(label='Raid Instanz', placeholder='z.B. Palast der Schatten')
    raid_date = ui.TextInput(label='Datum', placeholder='z.B. Mittwoch, 24.05.')
    raid_time = ui.TextInput(label='Uhrzeit', placeholder='19:45 - 22:30 Uhr')

    async def on_submit(self, interaction: discord.Interaction):
        category = discord.utils.get(interaction.guild.categories, id=RAID_CATEGORY_ID)
        channel = await interaction.guild.create_text_channel(f"raid-{self.raid_date.value}", category=category)
        
        embed = discord.Embed(title=f"⚔️ {self.raid_name.value}", color=discord.Color.green(),
                              description=f"📅 **Datum:** {self.raid_date.value}\n⏰ **Zeit:** {self.raid_time.value}")
        embed.add_field(name="Teilnehmer (0)", value="Noch keine Anmeldungen.", inline=False)
        
        await channel.send("@everyone", embed=embed, view=RaidView())
        await interaction.response.send_message(f"Raid-Channel {channel.mention} erstellt!", ephemeral=True)

class AdminControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="➕ Neuen Raid planen", style=discord.ButtonStyle.grey, custom_id="raid_bot:admin_setup")
    async def plan(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(RaidDetailModal())

class RaidBotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_planner(self, ctx):
        embed = discord.Embed(title="🛡️ Raid-Leitung", description="Klicke unten, um einen neuen Raid zu erstellen.", color=discord.Color.blue())
        await ctx.send(embed=embed, view=AdminControlView())

async def setup(bot):
    await bot.add_cog(RaidBotCog(bot))