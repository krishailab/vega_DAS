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

print("Starting migration of existing parts to include their process arrays...")

# 1. Map processes to their parent part_id
part_to_processes = {}
proc_cursor = processes_col.find({}, {"part_id": 1, "name": 1})
for p in proc_cursor:
    part_id = p.get("part_id")
    name = p.get("name")
    if part_id and name:
        part_to_processes.setdefault(part_id, []).append(name)

migrated_count = 0

parts_cursor = parts_col.find({})
for part in parts_cursor:
    part_id = part.get("part_id")
    # Fetch all processes mapped to this part
    associated_processes = part_to_processes.get(part_id, [])
    
    # Update the part document with the list of processes
    parts_col.update_one(
        {"part_id": part_id},
        {"$set": {"processes": associated_processes}}
    )
    print(f"Updated Part '{part.get('name')}' ({part_id}) -> Processes: {associated_processes}")
    migrated_count += 1

print(f"\nMigration complete! Scanned and updated {migrated_count} parts with their process lists.")
