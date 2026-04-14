import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import re
import aiohttp
from datetime import datetime, timedelta

# --- KONFIGURATION ---
# IDs als Umgebungsvariablen oder hier direkt eintragen
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)

# WoW Klassenfarben (Hex-Codes)
CLASS_COLORS = {
    "Death Knight": 0xC41E3A, "Demon Hunter": 0xA330C9, "Druid": 0xFF7C0A,
    "Evoker": 0x33937F, "Hunter": 0xAAD372, "Mage": 0x3FC7EB,
    "Monk": 0x00FF98, "Paladin": 0xF48CBA, "Priest": 0xFFFFFF,
    "Rogue": 0xFFF468, "Shaman": 0x0070DD, "Warlock": 0x8788EE,
    "Warrior": 0xC69B6D
}

def get_raid_week_dates():
    """Berechnet den Zeitraum von Donnerstag (Raid-Start) bis nächsten Mittwoch."""
    now = datetime.now()
    # Finde den letzten Donnerstag (Wochentag 3)
    days_since_thursday = (now.weekday() - 3) % 7
    last_thursday = now - timedelta(days=days_since_thursday)
    next_wednesday = last_thursday + timedelta(days=6)
    return last_thursday.strftime("%d.%m."), next_wednesday.strftime("%d.%m.")

# --- 1. RAID UMFRAGE LOGIK (START DONNERSTAG) ---
class RaidPollView(discord.ui.View):
    def __init__(self, week_range):
        super().__init__(timeout=None)
        self.week_range = week_range
        # Sortierung ab Donnerstag nach Weekly Reset
        self.days_order = ["Donnerstag", "Freitag", "Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch"]
        self.votes = {day: [] for day in self.days_order}

    async def update_poll_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"⚔️ Raid-Umfrage ({self.week_range})",
            description="Markiert alle Tage, an denen ihr Zeit habt!",
            color=discord.Color.blue()
        )
        for day in self.days_order:
            voters = self.votes[day]
            count = len(voters)
            voter_mentions = ", ".join([f"<@{v_id}>" for v_id in voters]) if voters else "Keine Stimmen"
            embed.add_field(name=f"{day} ({count})", value=voter_mentions, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_vote(self, interaction: discord.Interaction, day: str):
        user_id = interaction.user.id
        if user_id in self.votes[day]:
            self.votes[day].remove(user_id)
        else:
            self.votes[day].append(user_id)
        await self.update_poll_embed(interaction)

    @discord.ui.button(label="Do", style=discord.ButtonStyle.gray, custom_id="p_do")
    async def v_do(self, i, b): await self.handle_vote(i, "Donnerstag")
    @discord.ui.button(label="Fr", style=discord.ButtonStyle.gray, custom_id="p_fr")
    async def v_fr(self, i, b): await self.handle_vote(i, "Freitag")
    @discord.
