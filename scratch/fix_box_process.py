import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import parts_collection, processes_collection, stations_collection, users_collection
from app.utils import generate_custom_id, get_current_time

print("Starting deep clean and correction for BOX part & process IDs...")

# 1. Clean up duplicate BOX parts
box_parts = list(parts_collection.find({"name": "BOX"}))
print(f"Found {len(box_parts)} BOX part document(s) in parts_collection.")

target_part_id = "PTR26AAAA0009"

# Delete all parts with name BOX first to start clean, then insert with correct unique ID
parts_collection.delete_many({"name": "BOX"})

# Create/Ensure BOX part with PTR26AAAA0009 exists
box_part = {
    "part_id": target_part_id,
    "name": "BOX",
    "type": "HELMET",
    "processes": ["BOX"],
    "active": True
}
parts_collection.insert_one(box_part)
print(f"Set unique BOX part with Part ID: {target_part_id}")

# 2. Correct the process in processes_collection
processes_collection.delete_many({"name": "BOX"})

target_process_id = "PRO26AAAA0015"
box_process = {
    "process_id": target_process_id,
    "name": "BOX",
    "part_id": target_part_id,
    "part_name": "BOX",
    "step": 1,
    "created_by": "SYSTEM",
    "created_at": get_current_time()
}
processes_collection.insert_one(box_process)
print(f"Set unique BOX process in processes_collection with Process ID: {target_process_id} linked to Part ID: {target_part_id}")

# 3. Update stations that were pointing to the BOX part
# Both old part_id PTR26AAAA0010 and new target_part_id PTR26AAAA0009 (just in case)
stations_updated = stations_collection.update_many(
    {"$or": [{"part_id": target_part_id}, {"part_id": "PTR26AAAA0010", "process": "BOX"}]},
    {"$set": {"part_id": target_part_id, "process": "BOX", "process_id": target_process_id}}
)
print(f"Updated {stations_updated.modified_count} stations to point to target BOX part and process.")

# 4. Update users / Master Admins mapped to BOX
users_updated = users_collection.update_many(
    {"$or": [{"part_id": target_part_id}, {"part_id": "PTR26AAAA0010", "process_name": "BOX"}]},
    {"$set": {"part_id": target_part_id, "process_id": target_process_id, "process_name": "BOX"}}
)
print(f"Updated {users_updated.modified_count} users to point to correct BOX part and process.")

print("\nBOX part & process cleanup finished successfully!")
