import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

stations_col = db["stations"]
processes_col = db["processes"]

print("Starting migration of existing stations to add process_id...")

stations_cursor = stations_col.find({})
migrated_count = 0
not_found_count = 0

for station in stations_cursor:
    station_id = station.get("station_id")
    p_name = station.get("process")
    part_id = station.get("part_id")
    
    if p_name and part_id:
        proc = processes_col.find_one({"name": p_name.strip(), "part_id": part_id})
        if proc:
            proc_id = proc.get("process_id")
            stations_col.update_one(
                {"station_id": station_id},
                {"$set": {"process_id": proc_id}}
            )
            print(f"Updated station '{station.get('name')}' ({station_id}): process '{p_name}' -> process_id '{proc_id}'")
            migrated_count += 1
        else:
            print(f"WARNING: Process '{p_name}' not found for part_id '{part_id}' (station: '{station.get('name')}')")
            not_found_count += 1
    else:
        print(f"SKIPPED: Station '{station.get('name')}' ({station_id}) lacks process or part_id.")

print(f"\nMigration complete! Total stations updated: {migrated_count}. Missing process lookups: {not_found_count}")
