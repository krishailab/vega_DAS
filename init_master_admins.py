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

def init_master_admins():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    parts_col = db["parts"]
    

    # 2. Create Parts
    parts_data = [
        {"name": "Shell", "type": "Body", "process_id": "PRO26AA0001"},
        {"name": "Visor", "type": "Component", "process_id": "PRO26AA0002"},
        {"name": "Liner", "type": "Interior", "process_id": "PRO26AA0003"}
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

    # 3. Create Master Admins
    admins_to_create = [
        {
            "first_name": "Shell",
            "last_name": "Admin",
            "mobile_number": "9123456700",
            "email": "shell@vega.com",
            "part_name": "Shell"
        },
        {
            "first_name": "Visor",
            "last_name": "Admin",
            "mobile_number": "9123456701",
            "email": "visor@vega.com",
            "part_name": "Visor"
        },
        {
            "first_name": "Liner",
            "last_name": "Admin",
            "mobile_number": "9123456702",
            "email": "liner@vega.com",
            "part_name": "Liner"
        }
    ]
    
    hashed_pw = get_password_hash("123")
    
    for a in admins_to_create:
        if users_col.find_one({"email": a["email"]}):
            print(f"User {a['email']} already exists. Skipping.")
            continue
            
        user_doc = {
            "user_id": generate_custom_id("EMP", users_col, "user_id"),
            "first_name": a["first_name"],
            "last_name": a["last_name"],
            "age": 30,
            "gender": "M",
            "blood_group": "O+",
            "employee_id": f"VEGA_MA_{a['mobile_number'][-4:]}",
            "mobile_number": a["mobile_number"],
            "email": a["email"],
            "role": "Master Admin",
            "password": hashed_pw,
            "shift": "Day",
            "part_id": part_id_map[a["part_name"]]
        }
        
        users_col.insert_one(user_doc)
        print(f"Created Master Admin: {a['email']} (Part: {a['part_name']})")

    print("\n✅ Initialization complete!")

if __name__ == "__main__":
    init_master_admins()
