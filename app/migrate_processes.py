import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

processes_col = db["processes"]
users_col = db["users"]
parts_col = db["parts"]

print("Starting migration of existing processes...")

# 1. Build a cache mapping user_id -> part_id
user_to_part = {}
users_cursor = users_col.find({}, {"user_id": 1, "part_id": 1})
for u in users_cursor:
    uid = u.get("user_id")
    pid = u.get("part_id")
    if uid and pid:
        user_to_part[uid] = pid

# 2. Build a cache mapping part_id -> part_name
part_id_to_name = {}
parts_cursor = parts_col.find({}, {"part_id": 1, "name": 1})
for p in parts_cursor:
    pid = p.get("part_id")
    name = p.get("name")
    if pid and name:
        part_id_to_name[pid] = name

# Find a default part to fallback on if no part is mapped to the creator admin
default_part = parts_col.find_one({}, {"part_id": 1, "name": 1})
default_part_id = default_part.get("part_id") if default_part else None
default_part_name = default_part.get("name") if default_part else None

migrated_count = 0

processes_cursor = processes_col.find({})
for proc in processes_cursor:
    proc_id = proc.get("process_id")
    creator = proc.get("created_by")
    
    current_part_id = proc.get("part_id")
    current_part_name = proc.get("part_name")
    
    # Only update if it does not already have a valid part_id
    if not current_part_id:
        target_part_id = user_to_part.get(creator) or default_part_id
        target_part_name = part_id_to_name.get(target_part_id) or default_part_name
        
        if target_part_id:
            processes_col.update_one(
                {"process_id": proc_id},
                {"$set": {"part_id": target_part_id, "part_name": target_part_name}}
            )
            print(f"Migrated process '{proc.get('name')}' ({proc_id}) -> Part ID: {target_part_id} ({target_part_name})")
            migrated_count += 1
        else:
            print(f"WARNING: Process '{proc.get('name')}' ({proc_id}) has no creator part_id and no database parts exist to fall back on.")

print(f"\nMigration complete! Total processes migrated: {migrated_count}")
