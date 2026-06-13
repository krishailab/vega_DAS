import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

users_col = db["users"]
processes_col = db["processes"]
parts_col = db["parts"]

print("Starting migration of existing Master Admins...")

# Cache processes by parent part_id
part_to_process = {}
proc_cursor = processes_col.find({}, {"process_id": 1, "name": 1, "part_id": 1})
for p in proc_cursor:
    part_id = p.get("part_id")
    proc_id = p.get("process_id")
    proc_name = p.get("name")
    if part_id:
        part_to_process[part_id] = (proc_id, proc_name)

migrated_count = 0

master_admins = users_col.find({"role": "Master Admin"})
for admin in master_admins:
    user_id = admin.get("user_id")
    part_id = admin.get("part_id")
    current_proc_id = admin.get("process_id")
    
    if not current_proc_id and part_id:
        mapped = part_to_process.get(part_id)
        if mapped:
            proc_id, proc_name = mapped
            users_col.update_one(
                {"user_id": user_id},
                {"$set": {"process_id": proc_id, "process_name": proc_name}}
            )
            print(f"Migrated Master Admin '{admin.get('first_name')} {admin.get('last_name')}' ({user_id}) -> Process: {proc_id} ({proc_name})")
            migrated_count += 1
        else:
            # If no direct process exists for this part_id, find a generic one
            first_proc = processes_col.find_one({}, {"process_id": 1, "name": 1})
            if first_proc:
                proc_id = first_proc.get("process_id")
                proc_name = first_proc.get("name")
                users_col.update_one(
                    {"user_id": user_id},
                    {"$set": {"process_id": proc_id, "process_name": proc_name}}
                )
                print(f"Migrated Master Admin '{admin.get('first_name')} {admin.get('last_name')}' ({user_id}) -> Fallback Process: {proc_id} ({proc_name})")
                migrated_count += 1

print(f"\nMigration complete! Total Master Admins migrated: {migrated_count}")
