import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

reasons_col = db["reasons"]
processes_col = db["processes"]

print("Starting migration of existing reasons...")

# 1. Cache processes by creator or name to link logically
processes_by_creator = {}
proc_cursor = processes_col.find({}, {"process_id": 1, "name": 1, "created_by": 1})
for p in proc_cursor:
    creator = p.get("created_by")
    pid = p.get("process_id")
    name = p.get("name")
    if creator:
        processes_by_creator.setdefault(creator, []).append((pid, name))

# Grab a default process as a fallback
default_proc = processes_col.find_one({}, {"process_id": 1, "name": 1})
default_proc_id = default_proc.get("process_id") if default_proc else None
default_proc_name = default_proc.get("name") if default_proc else None

migrated_count = 0

reasons_cursor = reasons_col.find({})
for r in reasons_cursor:
    r_id = r.get("reason_id")
    creator = r.get("created_by")
    
    current_proc_id = r.get("process_id")
    if not current_proc_id:
        target_proc_id = None
        target_proc_name = None
        
        # Link to first process matching creator
        if creator in processes_by_creator and processes_by_creator[creator]:
            target_proc_id, target_proc_name = processes_by_creator[creator][0]
        else:
            target_proc_id = default_proc_id
            target_proc_name = default_proc_name
            
        if target_proc_id:
            reasons_col.update_one(
                {"reason_id": r_id},
                {"$set": {"process_id": target_proc_id, "process_name": target_proc_name}}
            )
            print(f"Migrated reason '{r.get('name')}' ({r_id}) -> Process: {target_proc_id} ({target_proc_name})")
            migrated_count += 1

print(f"\nMigration complete! Total reasons migrated: {migrated_count}")
