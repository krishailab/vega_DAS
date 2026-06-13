import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import stations_collection
for s in stations_collection.find({}):
    print(f"Station: {s.get('name')}, Process: {s.get('process')}, Process ID: {s.get('process_id')}, Part ID: {s.get('part_id')}")
