import os
import json
import discord
import asyncio
import aiohttp
import re
from quart import Quart, render_template_string, redirect, url_for, request
from datetime import datetime

app = Quart(__name__)

# --- KONFIGURATION ---
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
        # Säuberung der ID falls sie als String mit <@... landet
        self.applicant_id = int(re.sub(r'[^0-9]', '', str(applicant_id)))
        self.char_name = char_name

    @discord.ui.button(label="Annehmen", style=discord.ButtonStyle.green, custom_id="btn_accept", emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        if member:
            role_m, role_b = guild.get_role(MITGLIED_ROLLE_ID), guild.get_role(BEWERBER_ROLLE_ID)
            try:
                if role_b in member.roles: await member.remove_roles(role_b)
                await member.add_roles(role_m)
                await interaction.response.send_message(f"✅ **{self.char_name}** wurde aufgenommen!")
            except Exception as e: await interaction.response.send_message(f"Fehler: {e}", ephemeral=True)

# --- WEB DASHBOARD ROUTES ---

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
        # Reparatur-Logik für IDs mit <@...
        clean_uid = re.sub(r'[^0-9]', '', str(uid))
        role_info = {"name": "Gast", "color": "slate", "priority": 4}
        display_name = f"User {clean_uid}"
        
        if guild and clean_uid:
            try:
                mid = int(clean_uid)
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
            c_copy = char.copy()
            c_copy.update(live)
            c_copy['idx'] = idx
            processed_chars.append(c_copy)

        enhanced_list.append({"uid": clean_uid, "name": display_name, "chars": processed_chars, "role": role_info})

    enhanced_list.sort(key=lambda x: x['role']['priority'])

    html_template = """
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background: #0b1120; color: #e2e8f0; }
            .card-gradient { background: linear-gradient(135deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.8) 100%); }
        </style>
        <title>Gilden Dashboard</title>
    </head>
    <body class="p-4 md:p-10">
        <div class="container mx-auto max-w-6xl">
            <div class="bg-slate-900/60 p-8 rounded-3xl border border-slate-800 mb-10 shadow-2xl backdrop-blur-md">
                <h1 class="text-3xl font-black italic uppercase text-white mb-6">Gilden<span class="text-indigo-500">Management</span></h1>
                <form action="/add_applicant" method="post" class="flex flex-col md:flex-row gap-4">
                    <input name="rio_link" placeholder="Raider.io Link..." class="flex-grow bg-slate-800 border border-slate-700 px-4 py-3 rounded-xl outline-none focus:border-indigo-500 text-white" required>
                    <input name="discord_id" placeholder="Discord ID" class="md:w-1/4 bg-slate-800 border border-slate-700 px-4 py-3 rounded-xl outline-none focus:border-indigo-500 text-white" required>
                    <button type="submit" class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-8 py-3 rounded-xl transition-all uppercase text-sm">Hinzufügen</button>
                </form>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {% for user in members_list %}
                <div class="card-gradient rounded-3xl p-6 border border-slate-800 relative group transition-all shadow-xl">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <h2 class="text-xl font-bold text-white leading-tight">{{user.name}}</h2>
                            <span class="text-[10px] font-bold text-{{user.role.color}}-400 uppercase tracking-widest">{{user.role.name}}</span>
                        </div>
                        <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            {% if user.role.name == "Bewerber" %}
                            <a href="/action/accept/{{user.uid}}" class="p-2 bg-emerald-500/20 text-emerald-500 rounded-lg hover:bg-emerald-500 hover:text-white" title="Annehmen">✅</a>
                            {% endif %}
                            <a href="/full_delete/{{user.uid}}" class="p-2 bg-red-500/20 text-red-500 rounded-lg hover:bg-red-500 hover:text-white" onclick="return confirm('User komplett löschen?')">🗑️</a>
                        </div>
                    </div>

                    <div class="space-y-3">
                        {% for char in user.chars %}
                        <div class="bg-slate-950/50 p-4 rounded-2xl border border-slate-800 flex justify-between items-center group/char">
                            <div>
                                <p class="font-bold text-slate-100">{{char.name}}</p>
                                <p class="text-[10px] text-indigo-400 font-bold uppercase">{{char.class}} • {{char.ilvl}} iLvl</p>
                                <a href="{{char.rio_url}}" target="_blank" class="text-[9px] text-orange-500 font-black hover:underline mt-1 inline-block">RIO ↗</a>
                            </div>
                            <div class="flex gap-2 opacity-0 group-hover/char:opacity-100 transition-all">
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
                <h3 class="text-xl font-bold text-white mb-6">Charakter bearbeiten / Verschieben</h3>
                <form action="/edit_char" method="post" class="space-y-4">
                    <input type="hidden" name="old_uid" id="edit_uid">
                    <input type="hidden" name="char_idx" id="edit_idx">
                    
                    <div>
                        <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Discord ID (Besitzer)</label>
                        <input name="new_uid" id="display_uid" class="w-full bg-slate-950 border border-slate-700 px-4 py-2 rounded-xl text-indigo-400 font-mono outline-none focus:border-indigo-500">
                        <p class="text-[9px] text-slate-500 mt-1">Ändere die ID, um den Char einem anderen User zuzuweisen.</p>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Name</label>
                            <input name="new_name" id="edit_name" class="w-full bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl text-white outline-none">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">Server</label>
                            <input name="new_realm" id="edit_realm" class="w-full bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl text-white outline-none">
                        </div>
                    </div>
                    <div class="flex gap-3 pt-4">
                        <button type="submit" class="flex-grow bg-indigo-600 hover:bg-indigo-500 py-3 rounded-xl font-bold">Speichern</button>
                        <button type="button" onclick="closeEdit()" class="px-6 py-3 bg-slate-800 rounded-xl font-bold text-slate-400">Abbrechen</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            function openEdit(uid, idx, name, realm) {
                document.getElementById('edit_uid').value = uid;
                document.getElementById('display_uid').value = uid;
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

@app.route('/add_applicant', methods=['POST'])
async def add_applicant():
    form = await request.form
    rio_link = form.get('rio_link', '').strip()
    discord_id = re.sub(r'[^0-9]', '', form.get('discord_id', '').strip())
    
    if not rio_link or not discord_id: return redirect('/')
    name, realm = parse_rio_link(rio_link)
    if not name: return redirect('/')
    data = await fetch_char_data(name, realm)
    
    if bot_instance and bot_instance.is_ready():
        try:
            guild = bot_instance.get_guild(SERVER_ID)
            member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
            if member:
                role_b, role_g = guild.get_role(BEWERBER_ROLLE_ID), guild.get_role(GAST_ROLLE_ID)
                if role_g in member.roles: await member.remove_roles(role_g)
                await member.add_roles(role_b)
            
            forum_channel = bot_instance.get_channel(FORUM_CHANNEL_ID)
            if forum_channel:
                embed = discord.Embed(title=f"🛡️ Neue Bewerbung: {name}", color=0x3498db, timestamp=datetime.now())
                embed.add_field(name="Charakter", value=f"**{name}** - {data['class']} ({data['spec']})", inline=False)
                view = ActionButtons(discord_id, name)
                await forum_channel.create_thread(name=f"Bewerbung: {name}", embeds=[embed], view=view)
        except: pass

    with open(DB_FILE, "r+", encoding="utf-8") as f:
        try: db = json.load(f)
        except: db = {}
        if discord_id not in db: db[discord_id] = {"chars": []}
        if not any(c['name'].lower() == name.lower() for c in db[discord_id]["chars"]):
            db[discord_id]["chars"].append({"name": name, "realm": realm})
        f.seek(0); json.dump(db, f, indent=4, ensure_ascii=False); f.truncate()
    return redirect('/')

@app.route('/delete/<uid>/<int:char_idx>')
async def delete_char(uid, char_idx):
    clean_uid = re.sub(r'[^0-9]', '', str(uid))
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: db = json.load(f)
            except: db = {}
        
        # Kaputte Keys finden (mit <@)
        actual_key = uid if uid in db else next((k for k in db if re.sub(r'[^0-9]', '', str(k)) == clean_uid), None)
        
        if actual_key and 0 <= char_idx < len(db[actual_key]["chars"]):
            db[actual_key]["chars"].pop(char_idx)
            if not db[actual_key]["chars"]: del db[actual_key]
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=4, ensure_ascii=False)
    return redirect('/')

@app.route('/action/<action>/<uid>')
async def member_action(action, uid):
    clean_uid = re.sub(r'[^0-9]', '', str(uid))
    if bot_instance and bot_instance.is_ready():
        try:
            guild = bot_instance.get_guild(SERVER_ID)
            member = guild.get_member(int(clean_uid)) or await guild.fetch_member(int(clean_uid))
            if member:
                role_m, role_b, role_g = guild.get_role(MITGLIED_ROLLE_ID), guild.get_role(BEWERBER_ROLLE_ID), guild.get_role(GAST_ROLLE_ID)
                if action == "accept":
                    await member.remove_roles(role_b); await member.add_roles(role_m)
                elif action == "decline":
                    await member.remove_roles(role_b); await member.add_roles(role_g)
        except: pass
    return redirect('/')

@app.route('/full_delete/<uid>')
async def full_delete(uid):
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: db = json.load(f)
            except: db = {}
        if uid in db:
            del db[uid]
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=4, ensure_ascii=False)
    return redirect('/')

@app.route('/edit_char', methods=['POST'])
async def edit_char():
    form = await request.form
    old_uid = form.get('old_uid')
    new_uid = re.sub(r'[^0-9]', '', form.get('new_uid', '').strip())
    idx = int(form.get('char_idx'))
    new_name = form.get('new_name', '').strip()
    new_realm = form.get('new_realm', '').strip()

    if os.path.exists(DB_FILE) and new_uid:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try: db = json.load(f)
            except: db = {}
        
        # Erkennt sowohl saubere als auch kaputte (mit <@) IDs als Ursprung
        clean_old_uid = re.sub(r'[^0-9]', '', str(old_uid))
        actual_old_key = old_uid if old_uid in db else next((k for k in db if re.sub(r'[^0-9]', '', str(k)) == clean_old_uid), None)

        if actual_old_key and 0 <= idx < len(db[actual_old_key]["chars"]):
            char_data = db[actual_old_key]["chars"].pop(idx)
            char_data["name"] = new_name
            char_data["realm"] = new_realm

            if not db[actual_old_key]["chars"]:
                del db[actual_old_key]

            if new_uid not in db:
                db[new_uid] = {"chars": []}
            
            if not any(c['name'].lower() == new_name.lower() for c in db[new_uid]["chars"]):
                db[new_uid]["chars"].append(char_data)
            
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=4, ensure_ascii=False)
                
    return redirect('/')

async def run_web(bot=None):
    global bot_instance
    bot_instance = bot
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    config = Config()
    config.bind = [f"0.0.0.0:{os.environ.get('PORT', 5000)}"]
    await serve(app, config)