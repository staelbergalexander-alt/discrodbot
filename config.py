import os

# --- DISCORD ROLLEN IDS ---
# Diese IDs zieht sich der Bot direkt aus den Railway-Umgebungsvariablen
OFFIZIER_ROLLE_ID = int(os.getenv('OFFIZIER_ROLLE_ID') or 0)
MITGLIED_ROLLE_ID = int(os.getenv('MITGLIED_ROLLE_ID') or 0)
BEWERBER_ROLLE_ID = int(os.getenv('BEWERBER_ROLLE_ID') or 0)
GAST_ROLLE_ID = int(os.getenv('GAST_ROLLE_ID') or 0)

# --- CHANNEL IDS ---
FORUM_CHANNEL_ID = int(os.getenv('FORUM_CHANNEL_ID') or 0)
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID') or 0)
ARCHIV_CHANNEL_ID = int(os.getenv('ARCHIV_CHANNEL_ID') or 0)

# --- SERVER SETTINGS ---
SERVER_ID = int(os.getenv('SERVER_ID') or 0)

# --- DATEI-PFADE ---
# Pfade für das Railway-Volume, damit Daten nach einem Neustart bleiben
DB_FILE = "/app/data/mitglieder_db.json"
DASHBOARD_FILE = "/app/data/dashboard_config.json"
