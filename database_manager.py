import json
import os

DB_PATH = "data/mitglieder_db.json"

def load_db():
    if not os.path.exists(DB_PATH):
        return {"members": {}, "logs": []}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def add_member_to_db(member_id, name, status="Aktiv"):
    db = load_db()
    db["members"][str(member_id)] = {"name": name, "status": status}
    save_db(db)