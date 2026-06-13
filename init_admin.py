import os
import certifi
import bcrypt
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def get_current_time():
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

def init_users():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    parts_col = db["parts"]
    
    # 1. Create Parts if they don't exist
    parts_data = [
        {"name": "Shell", "type": "Body"},
        {"name": "Visor", "type": "Component"},
        {"name": "Liner", "type": "Interior"},
        {"name": "Cushion", "type": "Interior"},
        {"name": "Belt", "type": "Component"}
    ]
    
    part_id_map = {}
    for p in parts_data:
        existing = parts_col.find_one({"name": p["name"]})
        if existing:
            part_id_map[p["name"]] = existing["part_id"]
            print(f"Part {p['name']} already exists with ID {existing['part_id']}")
        else:
            p["part_id"] = generate_custom_id("PTR", parts_col, "part_id")
            p["active"] = True
            parts_col.insert_one(p)
            part_id_map[p["name"]] = p["part_id"]
            print(f"Created Part: {p['name']} ({p['part_id']})")

    # 2. Define Users from request
    # Format: Role, Mobile, First Name, Email
    users_to_create = [
        {"role": "Super Admin", "mobile": "9740561988", "first_name": "Karan", "email": "superadmin@vega.com", "last_name": "Admin", "department": "PRODUCTION"},
        {"role": "Super Admin", "mobile": "9740561901", "first_name": "Inventory", "email": "inventory.admin@vega.com", "last_name": "SuperAdmin", "department": "INVENTORY"},
        {"role": "Super Admin", "mobile": "9740561902", "first_name": "Purchase", "email": "purchase.admin@vega.com", "last_name": "SuperAdmin", "department": "PURCHASE"},
        {"role": "Super Admin", "mobile": "9740561903", "first_name": "Accounts", "email": "accounts.admin@vega.com", "last_name": "SuperAdmin", "department": "ACCOUNTS"},
        {"role": "Super Admin", "mobile": "9740561904", "first_name": "Sales", "email": "sales.admin@vega.com", "last_name": "SuperAdmin", "department": "SALES"},
        {"role": "Super Admin", "mobile": "9740561905", "first_name": "HR", "email": "hr.admin@vega.com", "last_name": "SuperAdmin", "department": "HR"},
        {"role": "Super Admin", "mobile": "9740561906", "first_name": "IT", "email": "it.admin@vega.com", "last_name": "SuperAdmin", "department": "IT"},
        {"role": "Super Admin", "mobile": "9740561907", "first_name": "R&D", "email": "rd.admin@vega.com", "last_name": "SuperAdmin", "department": "R&D"},
        
        {"role": "Master Admin", "mobile": "9234567890", "first_name": "Krish", "email": "Krish@vega.com", "last_name": "Shell Admin", "part_name": "Shell"},
        {"role": "Master Admin", "mobile": "9234567891", "first_name": "Harsh", "email": "Harsh@vega.com", "last_name": "Visor Admin", "part_name": "Visor"},
        {"role": "Master Admin", "mobile": "9234567892", "first_name": "Sandeep", "email": "Sandeep@vega.com", "last_name": "Liner Admin", "part_name": "Liner"},
        {"role": "Master Admin", "mobile": "9234567893", "first_name": "Sanju", "email": "Sanju@vega.com", "last_name": "Cushion Admin", "part_name": "Cushion"},
        {"role": "Master Admin", "mobile": "9234567894", "first_name": "Abaraj", "email": "Abaraj@vega.com", "last_name": "Belt Admin", "part_name": "Belt"},
        
        {"role": "Scanner", "mobile": "9234567881", "first_name": "Arjun", "email": "Arjun@vega.com", "last_name": "Scanner 1"},
        {"role": "Scanner", "mobile": "9234567882", "first_name": "Krishna", "email": "Krishna@vega.com", "last_name": "Scanner 2"},
        {"role": "Scanner", "mobile": "9234567883", "first_name": "Bheem", "email": "Bheem@vega.com", "last_name": "Scanner 3"},
        {"role": "Scanner", "mobile": "9234567884", "first_name": "Rahul", "email": "Rahul@vega.com", "last_name": "Scanner 4"},
        
        {"role": "Inspector", "mobile": "9234567871", "first_name": "Ramesh", "email": "Ramesh@vega.com", "last_name": "Inspector 1"},
        {"role": "Inspector", "mobile": "9234567872", "first_name": "Laxman", "email": "Laxman@vega.com", "last_name": "Inspector 2"},
        
        {"role": "Linker", "mobile": "9234567861", "first_name": "Raju", "email": "Raju@vega.com", "last_name": "Linker 1"},
        {"role": "Linker", "mobile": "9234567862", "first_name": "Chetan", "email": "Chetan@vega.com", "last_name": "Linker 2"},
        {"role": "B2B Admin", "mobile": "9740561910", "first_name": "B2B", "email": "b2badmin@vega.com", "last_name": "Admin", "department": "SALES"},
    ]
    
    hashed_pw = get_password_hash("123")
    master_admin_ids = {}
    for u in users_to_create:
        if u["role"] not in ["Super Admin", "Master Admin", "B2B Admin"]:
            continue
            
        existing = users_col.find_one({"email": u["email"]})
        if existing:
            print(f"User {u['email']} already exists. Updating...")
            user_id = existing["user_id"]
            users_col.update_one({"user_id": user_id}, {"$set": {
                "first_name": u["first_name"],
                "last_name": u["last_name"],
                "mobile_number": u["mobile"],
                "role": u["role"],
                "part_id": part_id_map.get(u.get("part_name")),
                "department": u.get("department", "PRODUCTION")
            }})
        else:
            user_id = generate_custom_id("EMP", users_col, "user_id")
            user_doc = {
                "user_id": user_id,
                "first_name": u["first_name"],
                "last_name": u["last_name"],
                "age": 30,
                "gender": "M",
                "blood_group": "O+",
                "employee_id": f"VEGA_{u['mobile'][-4:]}",
                "mobile_number": u["mobile"],
                "email": u["email"],
                "role": u["role"],
                "password": hashed_pw,
                "shift": "Day",
                "part_id": part_id_map.get(u.get("part_name")),
                "status": "Active",
                "department": u.get("department", "PRODUCTION")
            }
            users_col.insert_one(user_doc)
            print(f"Created {u['role']}: {u['email']}")
            
        if u["role"] == "Master Admin":
            master_admin_ids[u["part_name"]] = user_id

    default_master_admin_id = master_admin_ids.get("Shell")
    default_part_id = part_id_map.get("Shell")
    
    for u in users_to_create:
        if u["role"] in ["Super Admin", "Master Admin", "B2B Admin"]:
            continue
            
        existing = users_col.find_one({"email": u["email"]})
        if existing:
            print(f"User {u['email']} already exists. Updating...")
            users_col.update_one({"user_id": existing["user_id"]}, {"$set": {
                "first_name": u["first_name"],
                "last_name": u["last_name"],
                "mobile_number": u["mobile"],
                "role": u["role"],
                "department": "PRODUCTION"
            }})
        else:
            user_doc = {
                "user_id": generate_custom_id("EMP", users_col, "user_id"),
                "first_name": u["first_name"],
                "last_name": u["last_name"],
                "age": 25,
                "gender": "M",
                "blood_group": "B+",
                "employee_id": f"VEGA_{u['mobile'][-4:]}",
                "mobile_number": u["mobile"],
                "email": u["email"],
                "role": u["role"],
                "password": hashed_pw,
                "shift": "Day",
                "master_admin_id": default_master_admin_id,
                "part_id": default_part_id,
                "status": "Active",
                "department": "PRODUCTION"
            }
            if u["role"] == "Linker":
                user_doc["linker_capacity"] = 4
                
            users_col.insert_one(user_doc)
            print(f"Created {u['role']}: {u['email']}")

    print("\n✅ User initialization complete!")

if __name__ == "__main__":
    init_users()
