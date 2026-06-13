import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import parts_collection
parts_collection.update_one({"part_id": "PTR26AAAA0010"}, {"$set": {"processes": ["EXPORT", "DOMESTIC", "ECOMM"]}})
print("DISPATCH processes reset successfully!")
