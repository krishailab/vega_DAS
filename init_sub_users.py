import os
import certifi
import bcrypt
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def get_current_time():
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(IST).replace(tzinfo=None)

def generate_custom_id(prefix: str, collection, id_field: str) -> str:
    current_year = get_current_time().year
    yy = str(current_year)[-2:]
    
    count_this_year = collection.count_documents({id_field: {"$regex": f"^{prefix}{yy}"}})
    
    xx_index = count_this_year // 9999
    count = (count_this_year % 9999) + 1
    
    first_char = chr(65 + (xx_index // 26))
    second_char = chr(65 + (xx_index % 26))
    
    return f"{prefix}{yy}{first_char}{second_char}{count:04d}"

def init_sub_users():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    parts_col = db["parts"]
    
    print("Clearing all existing Scanner, Linker, and Inspector sub-users from the database...")
    del_result = users_col.delete_many({"role": {"$in": ["Scanner", "Linker", "Inspector"]}})
    print(f"Deleted {del_result.deleted_count} existing sub-users.")
    
    print("Resolving parent Master Admins dynamically...")
    master_admins = {}
    for parent_name in ["Shell", "Visor", "Liner"]:
        # Find a Master Admin whose assigned part name is parent_name
        part_doc = parts_col.find_one({"name": {"$regex": f"^{parent_name}$", "$options": "i"}})
        if part_doc:
            part_id = part_doc["part_id"]
            # Now find a Master Admin with this part_id
            m_admin = users_col.find_one({"role": "Master Admin", "part_id": part_id})
            if m_admin:
                master_admins[parent_name] = {
                    "user_id": m_admin["user_id"],
                    "part_id": part_id
                }
                print(f"Resolved parent '{parent_name}' -> Database Master Admin: {m_admin['first_name']} ({m_admin['user_id']})")
            else:
                # Fallback: Find a Master Admin whose email contains parent_name
                m_admin_fallback = users_col.find_one({"role": "Master Admin", "email": {"$regex": parent_name.lower(), "$options": "i"}})
                if m_admin_fallback:
                    master_admins[parent_name] = {
                        "user_id": m_admin_fallback["user_id"],
                        "part_id": m_admin_fallback.get("part_id")
                    }
                    print(f"Resolved parent '{parent_name}' via email fallback -> Database Master Admin: {m_admin_fallback['first_name']} ({m_admin_fallback['user_id']})")
        
        # If still not resolved, query any Master Admin containing the word
        if parent_name not in master_admins:
            m_admin_generic = users_col.find_one({"role": "Master Admin", "email": {"$regex": parent_name.lower(), "$options": "i"}})
            if m_admin_generic:
                master_admins[parent_name] = {
                    "user_id": m_admin_generic["user_id"],
                    "part_id": m_admin_generic.get("part_id")
                }
                print(f"Resolved parent '{parent_name}' via generic fallback -> Database Master Admin: {m_admin_generic['first_name']} ({m_admin_generic['user_id']})")

    # Sub-users to create
    sub_users_data = [
        # Shell Admin Sub-users
        {"first_name": "Shell", "role": "Scanner", "mobile": "9123456780", "parent": "Shell"},
        {"first_name": "Shell", "role": "Linker", "mobile": "9123456782", "parent": "Shell"},
        {"first_name": "Shell", "role": "Inspector", "mobile": "9123456908", "parent": "Shell"},
        
        # Visor Admin Sub-users
        {"first_name": "Visor", "role": "Scanner", "mobile": "9123456740", "parent": "Visor"},
        {"first_name": "Visor", "role": "Linker", "mobile": "9123456741", "parent": "Visor"},
        {"first_name": "Visor", "role": "Inspector", "mobile": "9123456742", "parent": "Visor"},
        
        # Liner Admin Sub-users
        {"first_name": "Liner", "role": "Scanner", "mobile": "9123456783", "parent": "Liner"},
        {"first_name": "Liner", "role": "Linker", "mobile": "9123456784", "parent": "Liner"},
        {"first_name": "Liner", "role": "Inspector", "mobile": "9123456785", "parent": "Liner"},
    ]
    
    hashed_pw = get_password_hash("123")
    total_created = 0
    
    for sub in sub_users_data:
        parent_key = sub["parent"]
        if parent_key not in master_admins:
            print(f"WARNING: Static parent Master Admin '{parent_key}' could not be resolved in the database. Skipping {sub['role']}.")
            continue
            
        parent_info = master_admins[parent_key]
        parent_id = parent_info["user_id"]
        
        # Fetch the actual Master Admin document from the database to dynamically inherit all matching keys
        m_admin = users_col.find_one({"user_id": parent_id})
        if not m_admin:
            print(f"WARNING: Parent Master Admin with ID {parent_id} not found. Skipping {sub['role']} for {parent_key}.")
            continue
            
        proc_id = m_admin.get("process_id")
        proc_name = m_admin.get("process_name")
        part_id = m_admin.get("part_id")
        plant_id = m_admin.get("plant_id")
        plant_name = m_admin.get("plant_name")
        plant_address = m_admin.get("plant_address")
        
        # Resolve Part Name
        part_name = "part"
        if part_id:
            part_doc = parts_col.find_one({"part_id": part_id})
            if part_doc:
                part_name = part_doc.get("name")
                
        clean_part_name = part_name.replace(" ", "").replace("&", "").replace("-", "").lower()
        clean_proc_name = proc_name.replace(" ", "").replace("&", "").replace("-", "").lower() if proc_name else "process"
        
        email = f"{clean_part_name}{clean_proc_name}.{sub['role'].lower()}@vega.com"
        
        # Check if sub-user already exists
        existing = users_col.find_one({
            "$or": [
                {"mobile_number": sub["mobile"]},
                {"email": email}
            ]
        })
        if existing:
            print(f"Sub-user {email} or mobile {sub['mobile']} already exists. Skipping.")
            continue
            
        user_id = generate_custom_id("EMP", users_col, "user_id")
        
        user_doc = {
            "user_id": user_id,
            "first_name": sub["first_name"],
            "last_name": sub["role"],
            "age": 25,
            "gender": "M",
            "blood_group": "B+",
            "employee_id": f"VEGA_SUB_{sub['mobile'][-4:]}",
            "mobile_number": sub["mobile"],
            "email": email,
            "role": sub["role"],
            "password": hashed_pw,
            "shift": "Day",
            "master_admin_id": parent_id,
            "linker_capacity": 4 if sub["role"] == "Linker" else 0, # Default capacity
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
        
        users_col.insert_one(user_doc)
        print(f"Created {sub['role']} for {parent_key} Admin: {email}")
        total_created += 1

    print(f"\n✅ Sub-user initialization complete! Total created: {total_created}")

if __name__ == "__main__":
    init_sub_users()
