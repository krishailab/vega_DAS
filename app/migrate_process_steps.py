import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

parts_col = db["parts"]
processes_col = db["processes"]

print("Starting step sequence migration for existing processes...")

migrated_count = 0

parts_cursor = parts_col.find({})
for part in parts_cursor:
    part_id = part.get("part_id")
    processes_list = part.get("processes", [])
    
    for idx, p_name in enumerate(processes_list):
        if not p_name.strip():
            continue
            
        result = processes_col.update_one(
            {"name": p_name.strip(), "part_id": part_id},
            {"$set": {"step": idx + 1}}
        )
        if result.modified_count > 0:
            print(f"Updated process '{p_name}' for part '{part.get('name')}' -> Step: {idx + 1}")
            migrated_count += 1

print(f"\nMigration complete! Updated step property for {migrated_count} processes.")
