import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

job_cards_col = db["job_cards"]
users_col = db["users"]
processes_col = db["processes"]

print("Starting migration of existing job cards to add plant_id, process_id, and process_name...")

process_map = {}
for p in processes_col.find({}, {"process_id": 1, "name": 1, "part_id": 1, "step": 1}):
    proc_id = p.get("process_id")
    if proc_id:
        process_map[proc_id] = p

part_process_map = {}
for p in process_map.values():
    part_id = p.get("part_id")
    if part_id:
        part_process_map.setdefault(part_id, []).append(p)

# Build user to plant/process map
user_map = {}
users_cursor = users_col.find({}, {"user_id": 1, "plant_id": 1, "process_id": 1, "process_name": 1})
for u in users_cursor:
    uid = u.get("user_id")
    proc_id = u.get("process_id")
    proc_name = u.get("process_name")
    if proc_id and not proc_name and proc_id in process_map:
        proc_name = process_map[proc_id].get("name")

    if uid:
        user_map[uid] = {
            "plant_id": u.get("plant_id"),
            "process_id": proc_id,
            "process_name": proc_name
        }

job_cards_cursor = job_cards_col.find({})
migrated_count = 0

for jc in job_cards_cursor:
    jc_id = jc.get("jobcard_id")
    creator_id = jc.get("created_by")
    
    if creator_id in user_map:
        plant_id = user_map[creator_id].get("plant_id")
        process_id = jc.get("process_id") or user_map[creator_id].get("process_id")
        process_name = jc.get("process_name") or user_map[creator_id].get("process_name")

        if process_id and not process_name and process_id in process_map:
            process_name = process_map[process_id].get("name")
    else:
        plant_id = jc.get("plant_id")
        process_id = jc.get("process_id")
        process_name = jc.get("process_name")

    if not process_id and jc.get("part_id"):
        part_processes = part_process_map.get(jc.get("part_id"), [])
        if len(part_processes) == 1:
            process_id = part_processes[0].get("process_id")
            process_name = part_processes[0].get("name")
        
    update_doc = {}
    if plant_id and not jc.get("plant_id"):
        update_doc["plant_id"] = plant_id
    if process_id and not jc.get("process_id"):
        update_doc["process_id"] = process_id
    if process_name and not jc.get("process_name"):
        update_doc["process_name"] = process_name
        
    if update_doc:
        job_cards_col.update_one(
            {"jobcard_id": jc_id},
            {"$set": update_doc}
        )
        print(f"Updated job card '{jc.get('jobcard_no')}' ({jc_id}) -> {update_doc}")
        migrated_count += 1

print(f"\nMigration complete! Total job cards updated: {migrated_count}")
