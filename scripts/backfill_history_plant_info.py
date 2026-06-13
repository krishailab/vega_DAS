"""
Migration: Backfill Plant Information in Process History
========================================================
This script updates existing scan, assembly, and dispatch records
to include the plant_id, plant_name, and plant_address of the user
who performed the action (scanner_id / linker_id).

Usage:
    PYTHONPATH=. venv/bin/python3 scripts/backfill_history_plant_info.py
"""

import os
from dotenv import load_dotenv
import certifi
from pymongo import MongoClient

load_dotenv()

def migrate():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    scans_col = db["scanner_processes"]
    asm_col = db["assembly_processes"]
    dsp_col = db["dispatch_processes"]

    # Preload users and their plant info
    users = list(users_col.find({"plant_id": {"$exists": True, "$ne": None}}))
    user_plant_map = {
        u["user_id"]: {
            "plant_id": u.get("plant_id"),
            "plant_name": u.get("plant_name"),
            "plant_address": u.get("plant_address"),
        }
        for u in users
    }
    
    print(f"Loaded {len(user_plant_map)} users with plant assignments.")

    def update_collection(collection, user_field, collection_name):
        print(f"\nProcessing {collection_name}...")
        records = list(collection.find({"plant_id": {"$exists": False}}))
        print(f"Found {len(records)} records needing plant info.")
        
        updated = 0
        skipped = 0
        for rec in records:
            uid = rec.get(user_field)
            if uid and uid in user_plant_map:
                plant_info = user_plant_map[uid]
                collection.update_one(
                    {"_id": rec["_id"]},
                    {"$set": plant_info}
                )
                updated += 1
            else:
                skipped += 1
                
        print(f"  ✓ Updated: {updated}")
        print(f"  - Skipped (user not found or no plant): {skipped}")
        return updated

    total = 0
    total += update_collection(scans_col, "scanner_id", "scanner_processes")
    total += update_collection(asm_col, "linker_id", "assembly_processes")
    total += update_collection(dsp_col, "linker_id", "dispatch_processes")

    print(f"\n{'─'*55}")
    print(f"✓ Migration complete! Total records updated: {total}")
    print(f"{'─'*55}\n")

if __name__ == "__main__":
    migrate()
