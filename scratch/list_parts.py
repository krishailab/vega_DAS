import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import parts_collection
for p in parts_collection.find({}):
    print(f"Part ID: {p.get('part_id')}, Part Name: {p.get('name')}, Type: {p.get('type')}, Processes: {p.get('processes')}")
