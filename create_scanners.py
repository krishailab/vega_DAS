import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import users_collection
from app.auth import get_password_hash
from app.utils import generate_custom_id, get_current_time

users_to_create = [
    {"first_name": "Kuber", "phone_number": "9036825548"},
    {"first_name": "athrav", "phone_number": "6363540158"}
]

password = "123"
hashed_password = get_password_hash(password)

for user_data in users_to_create:
    # Check if user already exists
    existing_user = users_collection.find_one({"phone_number": user_data["phone_number"]})
    if existing_user:
        print(f"User with phone number {user_data['phone_number']} already exists. Skipping.")
        continue

    user_id = generate_custom_id("EMP", users_collection, "user_id")
    
    new_user = {
        "user_id": user_id,
        "first_name": user_data["first_name"],
        "last_name": "",
        "age": 30,
        "gender": "M",
        "blood_group": "O+",
        "employee_id": f"VEGA_{user_data['phone_number'][-4:]}",
        "mobile_number": user_data["phone_number"],
        "email": f"{user_data['first_name'].lower()}@example.com", # Dummy email

        "password": hashed_password,
        "role": "Scanner",
        "master_admin_id": None, # Will be assigned when they log in and assign a station
        "linker_capacity": 2, # Default capacity, can be updated later
        "global_qr_number": 0,
        "assigned_station_id": None,
        "assigned_station_name": None,
        "created_at": get_current_time()
    }
    
    users_collection.insert_one(new_user)
    print(f"Created Scanner: {user_data['first_name']} (Phone: {user_data['phone_number']}, ID: {user_id})")

print("Finished creating users.")
