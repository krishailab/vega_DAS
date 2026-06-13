import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import users_collection
from app.auth import get_password_hash
from app.utils import generate_custom_id, get_current_time

users_to_create = [
    {"first_name": "Production", "last_name": "SuperAdmin", "phone_number": "9123456789", "email": "production@vegaauto.com", "department": "PRODUCTION"},
    {"first_name": "Inventory", "last_name": "SuperAdmin", "phone_number": "9123456788", "email": "inventory@vegaauto.com", "department": "INVENTORY"},
    {"first_name": "Purchase", "last_name": "SuperAdmin", "phone_number": "9123456787", "email": "purchase@vegaauto.com", "department": "PURCHASE"},
    {"first_name": "Accounts", "last_name": "SuperAdmin", "phone_number": "9123456786", "email": "accounts@vegaauto.com", "department": "ACCOUNTS"},
    {"first_name": "Sales", "last_name": "SuperAdmin", "phone_number": "9123456785", "email": "sales@vegaauto.com", "department": "SALES"},
    {"first_name": "HR", "last_name": "SuperAdmin", "phone_number": "9123456784", "email": "hr@vegaauto.com", "department": "HR"},
    {"first_name": "IT", "last_name": "SuperAdmin", "phone_number": "9123456783", "email": "it@vegaauto.com", "department": "IT"},
    {"first_name": "R&D", "last_name": "SuperAdmin", "phone_number": "9123456782", "email": "rd@vegaauto.com", "department": "R&D"}
]

password = "123"
hashed_password = get_password_hash(password)

for user_data in users_to_create:
    # Check if user already exists
    existing_user = users_collection.find_one({
        "$or": [
            {"mobile_number": user_data["phone_number"]},
            {"email": user_data["email"]}
        ]
    })
    if existing_user:
        print(f"User with phone number {user_data['phone_number']} or email {user_data['email']} already exists. Skipping.")
        continue

    user_id = generate_custom_id("EMP", users_collection, "user_id")
    
    new_user = {
        "user_id": user_id,
        "first_name": user_data["first_name"],
        "last_name": user_data["last_name"],
        "age": 30,
        "gender": "M",
        "blood_group": "O+",
        "employee_id": f"VEGA_{user_data['phone_number'][-4:]}",
        "mobile_number": user_data["phone_number"],
        "email": user_data["email"],
        "password": hashed_password,
        "role": "Super Admin",
        "master_admin_id": user_id, # Super admin is their own master admin usually, or None
        "linker_capacity": 0,
        "global_qr_number": 0,
        "assigned_station_id": None,
        "assigned_station_name": None,
        "department": user_data["department"],
        "created_at": get_current_time()
    }
    
    users_collection.insert_one(new_user)
    print(f"Created Super Admin: {user_data['first_name']} {user_data['last_name']} (Phone: {user_data['phone_number']}, ID: {user_id}, Dept: {user_data['department']})")

print("Finished creating user.")
