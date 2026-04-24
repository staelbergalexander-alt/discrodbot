import discord
from discord.ext import commands
from discord import ui
import sqlite3
import os

# --- KONFIGURATION ---
RAID_CATEGORY_ID = int(os.getenv('RAID_CATEGORY_ID') or 0)

WOW_DATA = {
    "Warrior": {"icon": "<:wowwarrior:1493404491045797918>", "Specs": {"Protection": "🛡️ Tank", "Fury": "⚔️ DD", "Arms": "⚔️ DD"}},
    "Paladin": {"icon": "<:wowpaladin:1493404654434783232>", "Specs": {"Protection": "🛡️ Tank", "Holy": "🌿 Heal", "Retribution": "⚔️ DD"}},
    "Death Knight": {"icon": "<:wowdeathknight:1493404419512074331>", "Specs": {"Blood": "🛡️ Tank", "Frost": "⚔️ DD", "Unholy": "⚔️ DD"}},
    "Hunter": {"icon": "<:wowhunter:1493404509945462906>", "Specs": {"Beast Mastery": "⚔️ DD", "Marksmanship": "⚔️ DD", "Survival": "⚔️ DD"}},
    "Shaman": {"icon": "<:wowshaman:1493404277748797470>", "Specs": {"Restoration": "🌿 Heal", "Elemental": "⚔️ DD", "Enhancement": "⚔️ DD"}},
    "Druid": {"icon": "<:wowdruid:1493404330420604999>", "Specs": {"Guardian": "🛡️ Tank", "Restoration": "🌿 Heal", "Balance": "⚔️ DD", "Feral": "⚔️ DD"}},
    "Rogue": {"icon": "<:wowrogue:1493404583534268517>", "Specs": {"Assassination": "⚔️ DD", "Outlaw": "⚔️ DD", "Subtlety": "⚔️ DD"}},
    "Monk": {"icon": "<:wowmonk:1493404364281217165>", "Specs": {"Brewmaster": "🛡️ Tank", "Mistweaver": "🌿 Heal", "Windwalker": "⚔️ DD"}},
    "Demon Hunter": {"icon": "<:wowdemonhunter:1493404389065359390>", "Specs": {"Havoc": "⚔️ DD", "Vengeance": "🛡️ Tank"}},
    "Evoker": {"icon": "<:evokerroundpng:1497024873011351672>", "Specs": {"Devastation": "⚔️ DD", "Preservation": "🌿 Heal", "Augmentation": "⚔️ DD"}},
    "Mage": {"icon": "<:wowmage:1493404551968063519>", "Specs": {"Frost": "⚔️ DD", "Fire": "⚔️ DD", "Arcane": "⚔️ DD"}},
    "Warlock": {"icon": "<:wowwarlock:1493404636370046996>", "Specs": {"Affliction": "⚔️ DD", "Demonology": "⚔️ DD", "Destruction": "⚔️ DD"}},
    "Priest": {"icon": "<:wowpriest:1493404618141470801>", "Specs": {"Discipline": "🌿 Heal", "Holy": "🌿 Heal", "Shadow": "⚔️ DD"}}
}

# --- DATENBANK INITIALISIERUNG ---
# Wir stellen sicher, dass die Tabelle existiert, SOBALD das Script geladen wird
def init_db():
    conn = sqlite3.connect('raid.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS signups 
                 (channel_id INTEGER, user_id INTEGER, user_name TEXT, 
                  wow_class TEXT, spec TEXT, role TEXT, is_late INTEGER DEFAULT 0,
                  PRIMARY KEY (channel_id, user_id))''')
    # Migration falls Spalte is_late fehlt
    try:
        c.execute("ALTER TABLE signups ADD COLUMN is_late INTEGER DEFAULT 0")
    except:
        pass
    conn.commit()
    conn.close()

init_db() # Sofort ausführen!

def update_db_signup(channel_id, user_id, name, wow_class=None, spec=None, role=None, is_late=False):
    conn = sqlite3.connect('raid.db')
    c = conn.cursor()
    
    if wow_class is None and not is_late:
        c.execute("DELETE FROM signups WHERE channel_id = ? AND user_id = ?", (channel_id, user_id))
    elif is_late:
        c.execute("UPDATE signups SET is_late = 1 WHERE channel_id = ? AND user_id = ?", (channel_id, user_id))
    else:
        c.execute("REPLACE INTO signups (channel_id, user_id, user_name, wow_class, spec, role, is_late) VALUES (?, ?, ?, ?, ?, ?, 0)", 
                  (channel_id, user_id, name, wow_class, spec, role))
    
    conn.commit()
    c.execute("SELECT user_name, wow_class, spec, role, is_late FROM signups WHERE channel_id = ?", (channel_id,))
    rows = c.fetchall()
    conn.close()
    return rows

async def update_raid_message(channel, all_signups):
    target_msg = None
    async for msg in channel.history(limit=20):
        if msg.author.id == channel.guild.me.id and msg.embeds:
            if msg.embeds[0].title and "⚔️" in msg.embeds[0].title:
                target_msg = msg
                break
    
    if not target_msg:
        return

    embed = target_msg.embeds[0]
    categories = {"🛡️ Tank": [], "🌿 Heal": [], "⚔️ DD": []}
    for name, w_class, s_db, r_db, is_late in all_signups:
        icon = WOW_DATA.get(w_class, {}).get("icon", "").strip()
        late_prefix = "⏰ " if is_late else ""
        if r_db in categories:
            categories[r_db].append(f"{late_prefix}{icon} **{name}** ({s_db})")
    
    embed.clear_fields()
    for r, m in categories.items():
        embed.add_field(name=f"{r} ({len(m)})", value="\n".join(m) if m else "None", inline=False)
    
    embed.set_footer(text=f"Total Participants: {len(all_signups)}")
    await target_msg.edit(embed=embed)

# --- UI ---

class SpecSelect(ui.Select):
    def __init__(self, wow_class, spec_options):
        super().__init__(placeholder=f"Spec for {wow_class}...", options=spec_options)
        self.wow_class = wow_class

    async def callback(self, interaction: discord.Interaction):
        spec, role = self.values[0].split("|")
        all_signups = update_db_signup(interaction.channel_id, interaction.user.id, interaction.user.display_name, self.wow_class, spec, role)
        await interaction.response.send_message(f"✅ Signed up as {spec} {self.wow_class}!", ephemeral=True)
        await update_raid_message(interaction.channel, all_signups)

class ClassSelect(ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, emoji=data["icon"].strip()) for name, data in WOW_DATA.items()]
        super().__init__(placeholder="Choose your Class...", options=options, custom_id="raid_bot:class_select")

    async def callback(self, interaction: discord.Interaction):
        chosen_class = self.values[0]
        specs = [discord.SelectOption(label=s, value=f"{s}|{r}", description=r) for s, r in WOW_DATA[chosen_class]["Specs"].items()]
        view = ui.View().add_item(SpecSelect(chosen_class, specs))
        await interaction.response.send_message(f"Which spec?", view=view, ephemeral=True)

class RaidView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClassSelect())

    @ui.button(label="Late Sign", style=discord.ButtonStyle.secondary, emoji="⏰", custom_id="raid_bot:late")
    async def late(self, interaction: discord.Interaction, button: ui.Button):
        all_signups = update_db_signup(interaction.channel_id, interaction.user.id, interaction.user.display_name, is_late=True)
        await interaction.response.send_message("⏰ Marked as late.", ephemeral=True)
        await update_raid_message(interaction.channel, all_signups)

    @ui.button(label="Sign Off", style=discord.ButtonStyle.red, custom_id="raid_bot:leave")
    async def leave(self, interaction: discord.Interaction, button: ui.Button):
        all_signups = update_db_signup(interaction.channel_id, interaction.user.id, interaction.user.display_name, None)
        await interaction.response.defer()
        await update_raid_message(interaction.channel, all_signups)

# --- ADMIN ---

class RaidDetailModal(ui.Modal, title='Raid Details'):
    raid_name = ui.TextInput(label='Raid Instance', placeholder='e.g., Palace')
    raid_date = ui.TextInput(label='Date', placeholder='e.g., 2024-11-20')
    raid_time = ui.TextInput(label='Time', placeholder='19:45')
    raid_info = ui.TextInput(label='Extra Info', style=discord.TextStyle.paragraph, required=False)

    def __init__(self, difficulty):
        super().__init__()
        self.difficulty = difficulty

    async def on_submit(self, interaction: discord.Interaction):
        if RAID_CATEGORY_ID == 0:
            return await interaction.response.send_message("❌ RAID_CATEGORY_ID error!", ephemeral=True)
        category = interaction.guild.get_channel(RAID_CATEGORY_ID)
        c_name = f"{self.difficulty.lower()}-{self.raid_name.value.replace(' ', '-')}"
        channel = await interaction.guild.create_text_channel(c_name, category=category)
        
        embed = discord.Embed(title=f"⚔️ {self.raid_name.value} ({self.difficulty})", color=discord.Color.green())
        embed.description = f"📅 **Date:** {self.raid_date.value}\n⏰ **Time:** {self.raid_time.value}\n📝 **Info:** {self.raid_info.value or 'None'}"
        embed.add_field(name="🛡️ Tank (0)", value="None", inline=False)
        embed.add_field(name="🌿 Heal (0)", value="None", inline=False)
        embed.add_field(name="⚔️ DD (0)", value="None", inline=False)
        
        await channel.send("""@everyone""", embed=embed, view=RaidView())
        await interaction.response.send_message(f"Raid channel {channel.mention} created!", ephemeral=True)

class DifficultySelect(ui.Select):
    def __init__(self):
        super().__init__(placeholder="Difficulty...", options=[
            discord.SelectOption(label="Normal"), discord.SelectOption(label="Heroic"), discord.SelectOption(label="Mythic")
        ])
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RaidDetailModal(self.values[0]))

class AdminControlView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label="➕ Plan New Raid", style=discord.ButtonStyle.grey, custom_id="raid_bot:admin_setup")
    async def plan(self, interaction: discord.Interaction, button: ui.Button):
        v = ui.View().add_item(DifficultySelect())
        await interaction.response.send_message("Select difficulty:", view=v, ephemeral=True)

class RaidBotCog(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_planner(self, ctx):
        await ctx.send(embed=discord.Embed(title="Raid Management", color=discord.Color.blue()), view=AdminControlView())

async def setup(bot): await bot.add_cog(RaidBotCog(bot))