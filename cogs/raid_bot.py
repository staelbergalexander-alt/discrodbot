import discord
from discord.ext import commands
from discord import ui
import sqlite3
import os

# --- KONFIGURATION ---
RAID_CATEGORY_ID = int(os.getenv('RAID_CATEGORY_ID') or 0)
WOW_DATA = {
    "Krieger": {"icon": "<:wowwarrior:1493404491045797918>", "Specs": {"Schutz": "🛡️ Tank", "Furor": "⚔️ DD", "Waffen": "⚔️ DD"}},
    "Paladin": {"icon": "<:wowpaladin:1493404654434783232>", "Specs": {"Schutz": "🛡️ Tank", "Heilig": "🌿 Heal", "Vergeltung": "⚔️ DD"}},
    "Todesritter": {"icon": "<:wowdeathknight:1493404419512074331>", "Specs": {"Blut": "🛡️ Tank", "Frost": "⚔️ DD", "Unheilig": "⚔️ DD"}},
    "Jäger": {"icon": "<:wowhunter:1493404509945462906>", "Specs": {"Tierherrschaft": "⚔️ DD", "Treffsicherheit": "⚔️ DD", "Überleben": "⚔️ DD"}},
    "Schamane": {"icon": "<:wowshaman:1493404277748797470>", "Specs": {"Wiederherstellung": "🌿 Heal", "Elementar": "⚔️ DD", "Verstärkung": "⚔️ DD"}},
    "Druide": {"icon": "<:wowdruid:1493404330420604999>", "Specs": {"Wächter": "🛡️ Tank", "Wiederherstellung": "🌿 Heal", "Gleichgewicht": "⚔️ DD", "Wildheit": "⚔️ DD"}},
    "Schurke": {"icon": "<:wowrogue:1493404583534268517>", "Specs": {"Meucheln": "⚔️ DD", "Gesetzlosigkeit": "⚔️ DD", "Täuschung": "⚔️ DD"}},
    "Mönch": {"icon": "<:wowmonk:1493404364281217165>", "Specs": {"Braumeister": "🛡️ Tank", "Nebelwirker": "🌿 Heal", "Windläufer": "⚔️ DD"}},
    "Dämonenjäger": {"icon": "<:wowdemonhunter:1493404389065359390>", "Specs": {"Verwüstung": "⚔️ DD", "Rache": "🛡️ Tank"}},
    "Rufer": {"icon": "<:evokerroundpng:1497024873011351672>", "Specs": {"Verheerung": "⚔️ DD", "Bewahrung": "🌿 Heal", "Verstärkung": "⚔️ DD"}},
    "Magier": {"icon": "<:wowmage:1493404551968063519>", "Specs": {"Frost": "⚔️ DD", "Feuer": "⚔️ DD", "Arkan": "⚔️ DD"}},
    "Hexenmeister": {"icon": "<:wowwarlock:1493404636370046996>", "Specs": {"Gebrechen": "⚔️ DD", "Dämonologie": "⚔️ DD", "Zerstörung": "⚔️ DD"}},
    "Priester": {"icon": "<:wowpriest:1493404618141470801>", "Specs": {"Disziplin": "🌿 Heal", "Heilig": "🌿 Heal", "Schatten": "⚔️ DD"}}
}

def update_db_signup(channel_id, user_id, name, wow_class=None, spec=None, role=None):
    conn = sqlite3.connect('raid.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS signups 
                 (channel_id INTEGER, user_id INTEGER, user_name TEXT, 
                  wow_class TEXT, spec TEXT, role TEXT, 
                  PRIMARY KEY (channel_id, user_id))''')
    if wow_class is None:
        c.execute("DELETE FROM signups WHERE channel_id = ? AND user_id = ?", (channel_id, user_id))
    else:
        c.execute("REPLACE INTO signups (channel_id, user_id, user_name, wow_class, spec, role) VALUES (?, ?, ?, ?, ?, ?)", 
                  (channel_id, user_id, name, wow_class, spec, role))
    conn.commit()
    c.execute("SELECT user_name, wow_class, spec, role FROM signups WHERE channel_id = ?", (channel_id,))
    rows = c.fetchall()
    conn.close()
    return rows

async def refresh_raid_embed(interaction, all_signups):
    embed = interaction.message.embeds[0]
    categories = {"🛡️ Tank": [], "🌿 Heal": [], "⚔️ DD": []}
    
    for name, w_class, spec, role in all_signups:
        class_icon = WOW_DATA.get(w_class, {}).get("icon", "")
        if role in categories:
            categories[role].append(f"{class_icon} **{name}** ({spec})")

    embed.clear_fields()
    for role, members in categories.items():
        count = len(members)
        val = "\n".join(members) if members else "Keine"
        embed.add_field(name=f"{role} ({count})", value=val, inline=False)

    embed.set_footer(text=f"Gesamtanzahl Teilnehmer: {len(all_signups)}")
    if interaction.response.is_done():
        await interaction.edit_original_response(view=RaidView()) # Workaround für Doppel-Response
        await interaction.message.edit(embed=embed)
    else:
        await interaction.response.edit_message(embed=embed)

class SpecSelect(ui.Select):
    def __init__(self, wow_class, options):
        super().__init__(placeholder=f"Spezialisierung für {wow_class}...", options=options)
        self.wow_class = wow_class

    async def callback(self, interaction: discord.Interaction):
        spec, role = self.values[0].split("|")
        all_signups = update_db_signup(interaction.channel_id, interaction.user.id, interaction.user.display_name, self.wow_class, spec, role)
        
        # Das ursprüngliche Raid-Embed suchen und updaten
        # Wir müssen hier die original_message finden
        channel = interaction.channel
        async for message in channel.history(limit=20):
            if message.author == interaction.client.user and len(message.embeds) > 0:
                if "Anmeldung" in message.embeds[0].title or "⚔️" in message.embeds[0].title:
                    categories = {"🛡️ Tank": [], "🌿 Heal": [], "⚔️ DD": []}
                    for name, w_class, spec_db, role_db in all_signups:
                        icon = WOW_DATA.get(w_class, {}).get("icon", "")
                        if role_db in categories:
                            categories[role_db].append(f"{icon} **{name}** ({spec_db})")
                    
                    new_embed = message.embeds[0]
                    new_embed.clear_fields()
                    for r, m in categories.items():
                        new_embed.add_field(name=f"{r} ({len(m)})", value="\n".join(m) if m else "Keine", inline=False)
                    new_embed.set_footer(text=f"Gesamtanzahl Teilnehmer: {len(all_signups)}")
                    
                    await message.edit(embed=new_embed)
                    await interaction.response.send_message(f"✅ Als {spec} ({self.wow_class}) angemeldet!", ephemeral=True)
                    return

class ClassSelect(ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=c, emoji=WOW_DATA[c]["icon"]) for c in WOW_DATA.keys()]
        super().__init__(placeholder="Wähle deine Klasse...", options=options, custom_id="raid_bot:class_select")

    async def callback(self, interaction: discord.Interaction):
        chosen_class = self.values[0]
        spec_options = [ui.SelectOption(label=s, value=f"{s}|{r}", description=r) for s, r in WOW_DATA[chosen_class]["Specs"].items()]
        view = ui.View(); view.add_item(SpecSelect(chosen_class, spec_options))
        await interaction.response.send_message(f"Welche Spec spielst du als {chosen_class}?", view=view, ephemeral=True)

class RaidView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClassSelect())

    @ui.button(label="Abmelden", style=discord.ButtonStyle.red, custom_id="raid_bot:leave")
    async def leave(self, interaction: discord.Interaction, button: ui.Button):
        all_signups = update_db_signup(interaction.channel_id, interaction.user.id, interaction.user.display_name, None)
        
        embed = interaction.message.embeds[0]
        categories = {"🛡️ Tank": [], "🌿 Heal": [], "⚔️ DD": []}
        for name, w_class, spec, role in all_signups:
            icon = WOW_DATA.get(w_class, {}).get("icon", "")
            if role in categories:
                categories[role].append(f"{icon} **{name}** ({spec})")
        
        embed.clear_fields()
        for r, m in categories.items():
            embed.add_field(name=f"{r} ({len(m)})", value="\n".join(m) if m else "Keine", inline=False)
        embed.set_footer(text=f"Gesamtanzahl Teilnehmer: {len(all_signups)}")
        await interaction.response.edit_message(embed=embed)

class RaidDetailModal(ui.Modal, title='Raid Details'):
    raid_name = ui.TextInput(label='Raid Instanz', placeholder='z.B. Palast der Schatten')
    raid_date = ui.TextInput(label='Datum', placeholder='z.B. 24-05')
    raid_time = ui.TextInput(label='Uhrzeit', placeholder='19:45')
    raid_info = ui.TextInput(label='Zusatz-Info', style=discord.TextStyle.paragraph, required=False)

    def __init__(self, difficulty):
        super().__init__()
        self.difficulty = difficulty

    async def on_submit(self, interaction: discord.Interaction):
        category = discord.utils.get(interaction.guild.categories, id=RAID_CATEGORY_ID)
        c_name = f"{self.difficulty.lower()}-{self.raid_name.value.replace(' ', '-')}-{self.raid_date.value}"
        channel = await interaction.guild.create_text_channel(c_name, category=category)
        
        embed = discord.Embed(title=f"⚔️ {self.raid_name.value} ({self.difficulty})", color=discord.Color.green(),
                              description=f"📅 **Datum:** {self.raid_date.value}\n⏰ **Zeit:** {self.raid_time.value}\n📝 **Info:** {self.raid_info.value or 'Keine'}")
        embed.add_field(name="🛡️ Tank (0)", value="Keine", inline=False)
        embed.add_field(name="🌿 Heal (0)", value="Keine", inline=False)
        embed.add_field(name="⚔️ DD (0)", value="Keine", inline=False)
        
        await channel.send("@everyone", embed=embed, view=RaidView())
        await interaction.response.send_message(f"Raid-Channel {channel.mention} erstellt!", ephemeral=True)

class DifficultySelect(ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Schwierigkeit...", 
            options=[
                discord.SelectOption(label="Normal"), 
                discord.SelectOption(label="Heroisch"), 
                discord.SelectOption(label="Mythisch")
            ]
        )
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RaidDetailModal(self.values[0]))

# 2. DANACH die Admin-View, die darauf zugreift
class AdminControlView(ui.View):
    def __init__(self): 
        super().__init__(timeout=None)

    @ui.button(label="➕ Neuen Raid planen", style=discord.ButtonStyle.grey, custom_id="raid_bot:admin_setup")
    async def plan(self, interaction: discord.Interaction, button: ui.Button):
        v = ui.View()
        v.add_item(DifficultySelect()) # Jetzt kennt Python die Klasse!
        await interaction.response.send_message("Bitte wähle die Schwierigkeit:", view=v, ephemeral=True)

class RaidBotCog(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_planner(self, ctx):
        await ctx.send(embed=discord.Embed(title="Raid-Leitung", color=discord.Color.blue()), view=AdminControlView())

async def setup(bot): await bot.add_cog(RaidBotCog(bot))