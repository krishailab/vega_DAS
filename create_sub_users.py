import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import users_collection
from app.auth import get_password_hash
from app.utils import generate_custom_id, get_current_time

print("Starting creation of sub-users for all Master Admins...")

# Fetch all Master Admins
master_admins = list(users_collection.find({"role": "Master Admin"}))
print(f"Found {len(master_admins)} Master Admins.")

password = "123"
hashed_password = get_password_hash(password)

sub_roles = ["Scanner", "Linker", "Inspector"]
total_created = 0

for m_admin in master_admins:
    m_id = m_admin["user_id"]
    m_name = m_admin["first_name"]
    proc_id = m_admin.get("process_id")
    proc_name = m_admin.get("process_name")
    part_id = m_admin.get("part_id")
    plant_id = m_admin.get("plant_id")
    plant_name = m_admin.get("plant_name")
    plant_address = m_admin.get("plant_address")
    
    clean_proc = proc_name.replace(" ", "").replace("&", "").replace("-", "").lower() if proc_name else "unknown"
    parent_phone_suffix = m_admin["mobile_number"][-3:]
    
    print(f"Processing sub-users for Master Admin: {m_name} ({m_id})...")
    
    for r_idx, role in enumerate(sub_roles, start=1):
        first_name = f"{m_name} {role}"
        email = f"{clean_proc}.{role.lower()}{parent_phone_suffix}@vegaauto.com"
        phone_number = f"9875{r_idx}5{parent_phone_suffix}"
        
        # Check if sub-user already exists
        existing = users_collection.find_one({
            "$or": [
                {"mobile_number": phone_number},
                {"email": email}
            ]
        })
        if existing:
            print(f"  Sub-user {email} already exists. Skipping.")
            continue
            
        user_id = generate_custom_id("EMP", users_collection, "user_id")
        
        new_sub = {
            "user_id": user_id,
            "first_name": first_name,
            "last_name": "SubUser",
            "age": 28,
            "gender": "M",
            "blood_group": "B+",
            "employee_id": f"VG_SUB_{role[0].upper()}_{phone_number[-3:]}",
            "mobile_number": phone_number,
            "email": email,
            "password": hashed_password,
            "role": role,
            "master_admin_id": m_id,
            "linker_capacity": 2 if role == "Linker" else 0, # Default linkage capacity for linkers
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
        
        users_collection.insert_one(new_sub)
        print(f"  Created Sub-User: {first_name} (ID: {user_id}, Phone: {phone_number})")
        total_created += 1

print(f"\nAll sub-user creation processes finished! Total sub-users created: {total_created}")
