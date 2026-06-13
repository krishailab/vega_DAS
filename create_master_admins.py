import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import users_collection, processes_collection, plants_collection, parts_collection
from app.auth import get_password_hash
from app.utils import generate_custom_id, get_current_time

process_ids = [
    "PRO26AAAA0001",
    "PRO26AAAA0002",
    "PRO26AAAA0003",
    "PRO26AAAA0004",
    "PRO26AAAA0005",
    "PRO26AAAA0006",
    "PRO26AAAA0007",
    "PRO26AAAA0008",
    "PRO26AAAA0009",
    "PRO26AAAA0010",
    "PRO26AAAA0011",
    "PRO26AAAA0012",
    "PRO26AAAA0013",
    "PRO26AAAA0014",
    "PRO26AAAA0015"
]

plant_id = "PLT26AAAA0001"

# Fetch Plant details
plant_doc = plants_collection.find_one({"plant_id": plant_id})
if plant_doc:
    plant_name = plant_doc.get("plant_name")
    plant_address = plant_doc.get("plant_address")
else:
    plant_name = "VEGA Belagavi"
    plant_address = "Plot No. 12-B, BEMCIEL Industrial Estate, Udyambag, Belagavi, Karnataka - 590008, India."

password = "123"
hashed_password = get_password_hash(password)

print(f"Starting creation of individual Master Admins for plant {plant_id}...")

for idx, proc_id in enumerate(process_ids, start=1):
    # Fetch Process details
    proc_doc = processes_collection.find_one({"process_id": proc_id})
    if not proc_doc:
        print(f"WARNING: Process {proc_id} not found in database. Skipping.")
        continue
        
    proc_name = proc_doc.get("name")
    part_id = proc_doc.get("part_id")
    
    part_name = "part"
    if part_id:
        part_doc = parts_collection.find_one({"part_id": part_id})
        if part_doc:
            part_name = part_doc.get("name")
            
    clean_part_name = part_name.replace(" ", "").replace("&", "").replace("-", "").lower()
    clean_proc_name = proc_name.replace(" ", "").replace("&", "").replace("-", "").lower()
    
    first_name = proc_name.title()
    email = f"{clean_part_name}{clean_proc_name}.admin@vegaauto.com"
    phone_number = f"9876543{idx:03d}"
    
    # Check if user already exists
    existing_user = users_collection.find_one({
        "$or": [
            {"mobile_number": phone_number},
            {"email": email},
            {"process_id": proc_id}
        ]
    })
    if existing_user:
        print(f"Master Admin for process {proc_id} / email {email} already exists. Skipping.")
        continue

    user_id = generate_custom_id("EMP", users_collection, "user_id")
    
    new_user = {
        "user_id": user_id,
        "first_name": first_name,
        "last_name": "MasterAdmin",
        "age": 35,
        "gender": "M",
        "blood_group": "A+",
        "employee_id": f"VG_MST_{phone_number[-3:]}",
        "mobile_number": phone_number,
        "email": email,
        "password": hashed_password,
        "role": "Master Admin",
        "master_admin_id": user_id,
        "linker_capacity": 0,
        "global_qr_number": 0,
        "assigned_station_id": None,
        "assigned_station_name": None,
        "department": "PRODUCTION",
        "plant_id": plant_id,
        "plant_name": plant_name,
        "plant_address": plant_address,
        "process_id": proc_id,
        "process_name": proc_name,
        "part_id": part_id,
        "status": "Active",
        "created_at": get_current_time()
    }
    
    users_collection.insert_one(new_user)
    print(f"Created Master Admin: {first_name} MasterAdmin (ID: {user_id}, Process: {proc_name}, Phone: {phone_number})")

print("All Master Admin creation processes finished!")
