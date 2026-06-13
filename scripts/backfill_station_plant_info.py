"""
Migration: Backfill Plant Information in Stations
=================================================
This script updates existing station records to include the
plant_id, plant_name, and plant_address by pulling it from
the Master Admin who created the station.

If the Master Admin doesn't have a plant assigned, it assigns
the first available plant to them, and then to the station.

Usage:
    PYTHONPATH=. venv/bin/python3 scripts/backfill_station_plant_info.py
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
    stations_col = db["stations"]
    plants_col = db["plants"]

    # Load plants for fallback
    plants = list(plants_col.find({}))
    if not plants:
        print("❌ No plants found in database! Create a plant first.")
        return
        
    fallback_plant = plants[0]
    fallback_info = {
        "plant_id": fallback_plant["plant_id"],
        "plant_name": fallback_plant.get("plant_name"),
        "plant_address": fallback_plant.get("plant_address"),
    }
    print(f"Fallback Plant loaded: {fallback_info['plant_name']} ({fallback_info['plant_id']})")

    # Preload Master Admins and their plant info
    master_admins = list(users_col.find({"role": "Master Admin"}))
    user_plant_map = {}
    for u in master_admins:
        if u.get("plant_id"):
            user_plant_map[u["user_id"]] = {
                "plant_id": u.get("plant_id"),
                "plant_name": u.get("plant_name"),
                "plant_address": u.get("plant_address"),
            }
        else:
            # Fix Master Admin who is missing plant
            users_col.update_one({"user_id": u["user_id"]}, {"$set": fallback_info})
            user_plant_map[u["user_id"]] = fallback_info
            print(f"Fixed missing plant for Master Admin: {u['user_id']}")
    
    print(f"\nProcessing stations...")
    stations = list(stations_col.find({"plant_id": {"$exists": False}}))
    print(f"Found {len(stations)} stations needing plant info.")
    
    updated = 0
    skipped = 0
    for station in stations:
        master_id = station.get("master_admin_id")
        if master_id and master_id in user_plant_map:
            plant_info = user_plant_map[master_id]
            stations_col.update_one(
                {"_id": station["_id"]},
                {"$set": plant_info}
            )
            updated += 1
        else:
            # Station has no master admin or master admin wasn't in list. Use fallback directly.
            stations_col.update_one(
                {"_id": station["_id"]},
                {"$set": fallback_info}
            )
            updated += 1
            
    print(f"  ✓ Updated: {updated}")
    print(f"  - Skipped: {skipped}")

    print(f"\n{'─'*55}")
    print(f"✓ Migration complete! Total stations updated: {updated}")
    print(f"{'─'*55}\n")

if __name__ == "__main__":
    migrate()
