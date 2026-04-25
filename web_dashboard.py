import os
import json
import discord
import asyncio
import aiohttp
import re
from quart import Quart, render_template_string, redirect, url_for, request
from datetime import datetime

app = Quart(__name__)

# Konfiguration
DB_FILE = "/app/data/mitglieder_db.json" if os.path.exists("/app/data/") else "data/mitglieder_db.json"
SERVER_ID = int(os.getenv('SERVER_ID') or 0)
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)

bot_instance = None

# --- HILFSFUNKTIONEN ---

def parse_rio_link(link):
    match = re.search(r'characters/eu/([^/]+)/([^/]+)', link)
    if match:
        realm = match.group(1).replace('-', ' ').title()
        name = match.group(2).title()
        return name, realm
    return None, None

async def fetch_char_data(name, realm):
    clean_name = name.strip().lower()
    clean_realm = realm.strip().lower().replace(" ", "-")
    url = f"https://raider.io/api/v1/characters/profile?region=eu&realm={clean_realm}&name={clean_name}&fields=gear"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "ilvl": data.get('gear', {}).get('item_level_equipped', 0),
                        "class": data.get('class', 'Unbekannt'),
                        "spec": data.get('active_spec_name', 'Unbekannt'),
                        "rio_url": f"https://raider.io/characters/eu/{clean_realm}/{clean_name}"
                    }
    except: pass
    return {"ilvl": "??", "class": "Unbekannt", "spec": "Unbekannt", "rio_url": f"https://raider.io/characters/eu/{clean_realm}/{clean_name}"}

# --- DISCORD INTERAKTION ---

class ActionButtons(discord.ui.View):
    def __init__(self, applicant_id=None, char_name=None):
        super().__init__(timeout=None)
        self.applicant_id = int(applicant_id)
        self.char_name = char_name

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.green, custom_id="btn_accept", emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        if member:
            role_mitglied = guild.get_role(MITGLIED_ROLLE_ID)
            role_bewerber = guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if role_bewerber in member.roles: await member.remove_roles(role_bewerber)
                await member.add_roles(role_mitglied)
                await interaction.response.send_message(f"✅ **{self.char_name}** wurde aufgenommen!", ephemeral=False)
            except Exception as e: await interaction.response.send_message(f"Fehler: {e}", ephemeral=True)
        else: await interaction.response.send_message("User nicht gefunden.", ephemeral=True)

# --- WEB DASHBOARD ---

@app.route('/')
async def index():
    members_data = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: members_data = json.load(f)
            except: pass

    enhanced_list = []
    guild = bot_instance.get_guild(SERVER_ID) if bot_instance and bot_instance.is_ready() else None

    for uid, user_data in members_data.items():
        role_info = {"name": "Gast", "color": "slate", "priority": 4}
        display_name = f"User {uid}"
        
        if guild:
            try:
                mid = int(uid)
                member = guild.get_member(mid) or await guild.fetch_member(mid)
                if member:
                    display_name = member.display_name
                    rids = [r.id for r in member.roles]
                    if OFFIZIER_ROLLE_ID in rids: role_info = {"name": "Offizier", "color": "violet", "priority": 1}
                    elif MITGLIED_ROLLE_ID in rids: role_info = {"name": "Mitglied", "color": "emerald", "priority": 2}
                    elif BEWERBER_ROLLE_ID in rids: role_info = {"name": "Bewerber", "color": "amber", "priority": 3}
            except: pass

        processed_chars = []
        for idx, char in enumerate(user_data.get("chars", [])):
            live = await fetch_char_data(char['name'], char.get('realm', 'Blackhand'))
            char_entry = char.copy()
            char_entry.update(live)
            char_entry['idx'] = idx # Wichtig für die Identifizierung beim Editieren
            processed_chars.append(char_entry)

        enhanced_list.append({"uid": uid, "name": display_name, "chars": processed_chars, "role": role_info})

    enhanced_list.sort(key=lambda x: x['role']['priority'])

    html_template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body { font-family: 'Inter', sans-serif; background: #0b1120; }
            .card-gradient { background: linear-gradient(135deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.8) 100%); }
        </style>
        <title>Gilden Dashboard</title>
    </head>
    <body class="text-slate-200 p-4 md:p-10">
        <div class="container mx-auto max-w-6xl">
            <div class="bg-slate-900/60 p-6 rounded-3xl border border-slate-800 mb-10 shadow-2xl">
                <h1 class="text-2xl font-black text-white mb-4 uppercase italic">Gilden<span class="text-indigo-500">Management</span></h1>
                <form action="/add_applicant" method="post" class="flex flex-col md:flex-row gap-4">
                    <input name="rio_link" placeholder="Raider.io Link..." class="flex-grow bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl text-white outline-none focus:border-indigo-500" required>
                    <input name="discord_id" placeholder="Discord ID" class="md:w-1/4 bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl text-white outline-none" required>
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 px-6 py-2 rounded-xl font-bold uppercase text-sm">Hinzufügen</button>
                </form>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {% for user in members_list %}
                <div class="card-gradient rounded-3xl p-6 border border-slate-800 relative group transition-all">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <h2 class="text-xl font-bold text-white">{{user.name}}</h2>
                            <span class="text-[10px] font-bold text-{{user.role.color}}-400 uppercase">{{user.role.name}}</span>
                        </div>
                        <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            {% if user.role.name == "Bewerber" %}
                            <a href="/action/accept/{{user.uid}}" class="text-emerald-500 hover:scale-110">✅</a>
                            {% endif %}
                            <a href="/full_delete/{{user.uid}}" class="text-red-500 hover:scale-110" onclick="return confirm('User komplett löschen?')">🗑️</a>
                        </div>
                    </div>

                    <div class="space-y-3">
                        {% for char in user.chars %}
                        <div class="bg-slate-950/50 p-4 rounded-2xl border border-slate-800 flex justify-between items-center group/char">
                            <div>
                                <p class="font-bold text-slate-100">{{char.name}}</p>
                                <p class="text-[10px] text-indigo-400 font-bold uppercase">{{char.class}} • {{char.ilvl}} iLvl</p>
                            </div>
                            <div class="flex gap-3 opacity-0 group-hover/char:opacity-100 transition-all">
                                <button onclick="openEdit('{{user.uid}}', '{{char.idx}}', '{{char.name}}', '{{char.realm}}')" class="text-slate-500 hover:text-indigo-400">✏️</button>
                                <a href="/delete/{{user.uid}}/{{char.idx}}" class="text-slate-500 hover:text-red-500">✕</a>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div id="editModal" class="hidden fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div class="bg-slate-900 border border-slate-800 p-8 rounded-3xl w-full max-w-md shadow-2xl">
                <h3 class="text-xl font-bold text-white mb-6">Charakter bearbeiten</h3>
                <form action="/edit_char" method="post" class="space-y-4">
                    <input type="hidden" name="uid" id="edit_uid">
                    <input type="hidden" name="char_idx" id="edit_idx">
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Name</label>
                        <input name="new_name" id="edit_name" class="w-full bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl text-white outline-none focus:border-indigo-500">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Server</label>
                        <input name="new_realm" id="edit_realm" class="w-full bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl text-white outline-none focus:border-indigo-500">
                    </div>
                    <div class="flex gap-3 pt-4">
                        <button type="submit" class="flex-grow bg-indigo-600 hover:bg-indigo-500 py-3 rounded-xl font-bold">Speichern</button>
                        <button type="button" onclick="closeEdit()" class="px-6 py-3 bg-slate-800 rounded-xl font-bold">Abbrechen</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            function openEdit(uid, idx, name, realm) {
                document.getElementById('edit_uid').value = uid;
                document.getElementById('edit_idx').value = idx;
                document.getElementById('edit_name').value = name;
                document.getElementById('edit_realm').value = realm;
                document.getElementById('editModal').classList.remove('hidden');
            }
            function closeEdit() {
                document.getElementById('editModal').classList.add('hidden');
            }
        </script>
    </body>
    </html>
    """
    return await render_template_string(html_template, members_list=enhanced_list)

@app.route('/edit_char', methods=['POST'])
async def edit_char():
    form = await request.form
    uid = form.get('uid')
    idx = int(form.get('char_idx'))
    new_name = form.get('new_name').strip()
    new_realm = form.get('new_realm').strip()

    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        
        if uid in db and 0 <= idx < len(db[uid]["chars"]):
            db[uid]["chars"][idx]["name"] = new_name
            db[uid]["chars"][idx]["realm"] = new_realm
            
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=4, ensure_ascii=False)
                
    return redirect('/')

# --- Restliche Routen (add_applicant, delete_char, full_delete, member_action) bleiben wie gehabt ---

@app.route('/add_applicant', methods=['POST'])
async def add_applicant():
    form = await request.form
    rio_link = form.get('rio_link', '').strip()
    discord_id = form.get('discord_id', '').strip()
    if not rio_link or not discord_id: return redirect('/')
    name, realm = parse_rio_link(rio_link)
    if not name: return redirect('/')
    data = await fetch_char_data(name, realm)
    if bot_instance and bot_instance.is_ready():
        guild = bot_instance.get_guild(SERVER_ID)
        member = guild.get_member(int(discord_id))
        if member:
            role_gast = guild.get_role(GAST_ROLLE_ID)
            role_bewerber = guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if role_gast in member.roles: await member.remove_roles(role_gast)
                await member.add_roles(role_bewerber)
            except: pass
        forum_channel = bot_instance.get_channel(FORUM_CHANNEL_ID)
        if forum_channel:
            embed = discord.Embed(title=f"🛡️ Neue Bewerbung: {name}", color=0x3498db, timestamp=datetime.now())
            embed.add_field(name="Charakter", value=f"**{name}** - {data['class']} ({data['spec']})", inline=False)
            view = ActionButtons(discord_id, name)
            content = f"🔗 [Raider.io Profile]({rio_link})"
            await forum_channel.create_thread(name=f"Bewerbung: {name}", embeds=[embed], content=content, view=view)
    with open(DB_FILE, "r+", encoding="utf-8") as f:
        try: db = json.load(f)
        except: db = {}
        if discord_id not in db: db[discord_id] = {"chars": []}
        if not any(c['name'] == name for c in db[discord_id]["chars"]):
            db[discord_id]["chars"].append({"name": name, "realm": realm})
        f.seek(0); json.dump(db, f, indent=4, ensure_ascii=False); f.truncate()
    return redirect('/')

@app.route('/delete/<uid>/<int:char_idx>')
async def delete_char(uid, char_idx):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            db = json.load(f)
        if uid in db and 0 <= char_idx < len(db[uid]["chars"]):
            db[uid]["chars"].pop(char_idx)
            if not db[uid]["chars"]: del db[uid]
            with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db, f, indent=4, ensure_ascii=False)
    return redirect('/')

@app.route('/action/<action>/<uid>')
async def member_action(action, uid):
    if bot_instance and bot_instance.is_ready():
        guild = bot_instance.get_guild(SERVER_ID)
        member = guild.get_member(int(uid)) or await guild.fetch_member(int(uid))
        if member:
            role_m, role_b, role_g = guild.get_role(MITGLIED_ROLLE_ID), guild.get_role(BEWERBER_ROLLE_ID), guild.get_role(GAST_ROLLE_ID)
            try:
                if action == "accept":
                    await member.remove_roles(role_b); await member.add_roles(role_m)
                elif action == "decline":
                    await member.remove_roles(role_b); await member.add_roles(role_g)
            except: pass
    return redirect('/')

@app.route('/full_delete/<uid>')
async def full_delete(uid):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: db = json.load(f)
        if uid in db:
            del db[uid]
            with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db, f, indent=4, ensure_ascii=False)
    return redirect('/')

async def run_web(bot=None):
    global bot_instance
    bot_instance = bot
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)