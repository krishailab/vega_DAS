import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import users_collection

users = users_collection.find({"mobile_number": {"$exists": False}})
for u in users:
    users_collection.update_one(
        {"_id": u["_id"]},
        {"$set": {
            "mobile_number": u.get("phone_number", ""),
            "age": 30,
            "gender": "M",
            "blood_group": "O+",
            "employee_id": f"VEGA_{u.get('phone_number', '0000')[-4:]}"
        }}
    )
print("Users fixed.")
