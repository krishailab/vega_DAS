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

def init_b2b_admin():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    
    u = {
        "role": "B2B Admin",
        "mobile": "9740561910",
        "first_name": "B2B",
        "last_name": "Admin",
        "email": "b2badmin@vega.com",
        "department": "SALES"
    }
    
    hashed_pw = get_password_hash("123")
    
    existing = users_col.find_one({"email": u["email"]})
    if existing:
        print(f"B2B Admin {u['email']} already exists. Updating...")
        user_id = existing["user_id"]
        users_col.update_one({"user_id": user_id}, {"$set": {
            "first_name": u["first_name"],
            "last_name": u["last_name"],
            "mobile_number": u["mobile"],
            "role": u["role"],
            "department": u["department"]
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
            "part_id": None,
            "status": "Active",
            "department": u["department"]
        }
        users_col.insert_one(user_doc)
        print(f"✓ Created B2B Admin: {u['email']} with ID: {user_id}")
        
    print("\n✅ B2B Admin initialization complete!")

if __name__ == "__main__":
    init_b2b_admin()
