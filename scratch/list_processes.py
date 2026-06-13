import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import processes_collection, parts_collection
for p in processes_collection.find({}):
    part = parts_collection.find_one({"part_id": p.get("part_id")})
    part_name = part.get("name") if part else "None"
    print(f"Process ID: {p.get('process_id')}, Process Name: {p.get('name')}, Part ID: {p.get('part_id')}, Part Name: {part_name}, Step: {p.get('step')}")
