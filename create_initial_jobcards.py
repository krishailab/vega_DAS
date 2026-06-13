import os
import certifi
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

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

def generate_custom_ids(prefix: str, collection, id_field: str, quantity: int) -> list:
    current_year = get_current_time().year
    yy = str(current_year)[-2:]
    count_this_year = collection.count_documents({id_field: {"$regex": f"^{prefix}{yy}"}})
    
    ids = []
    for i in range(quantity):
        idx = count_this_year + i
        xx_index = idx // 9999
        count = (idx % 9999) + 1
        first_char = chr(65 + (xx_index // 26))
        second_char = chr(65 + (xx_index % 26))
        ids.append(f"{prefix}{yy}{first_char}{second_char}{count:04d}")
    return ids

def create_jobcards():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    job_cards_col = db["job_cards"]
    qr_master_col = db["qr_master"]
    parts_col = db["parts"]
    
    # 1. Identify Master Admins
    master_admins = list(users_col.find({"role": "Master Admin"}))
    if not master_admins:
        print("No Master Admins found.")
        return
        
    print(f"Found {len(master_admins)} Master Admins.")
    
    for admin in master_admins:
        admin_id = admin["user_id"]
        part_id = admin.get("part_id")
        admin_name = admin["first_name"]
        
        if not part_id:
            print(f"Skipping {admin_name}: No part assigned to profile.")
            continue
            
        part = parts_col.find_one({"part_id": part_id})
        part_name = part["name"] if part else "Unknown Model"
            
        print(f"\nCreating Job Card for {admin_name} ({part_name})...")
        
        # Generate Job Card ID
        jbc_id = generate_custom_id("JBC", job_cards_col, "jobcard_id")
        jbc_no = f"JC-{admin_name.upper()}-2026-001"
        
        job_card_doc = {
            "jobcard_id": jbc_id,
            "jobcard_no": jbc_no,
            "jobcard_date": get_current_time().strftime("%Y-%m-%d"),
            "part_id": part_id,
            "part_model": part_name,
            "part_composition": "Standard Material",
            "quantity": 20,
            "created_by": admin_id,
            "created_at": get_current_time(),
            "status": "IN PROGRESS"
        }
        
        job_cards_col.insert_one(job_card_doc)
        print(f"  Created Job Card: {jbc_no} ({jbc_id})")
        
        # Generate 20 QRs
        qr_ids = generate_custom_ids("PRD", qr_master_col, "qr_id", 20)
        qr_records = []
        for qr_id in qr_ids:
            qr_records.append({
                "qr_id": qr_id,
                "jobcard_id": jbc_id,
                "part_id": part_id,
                "master_admin_id": admin_id,
                "status": "UNUSED",
                "created_at": get_current_time()
            })
            
        if qr_records:
            qr_master_col.insert_many(qr_records)
            print(f"  Generated 20 QR codes (Start: {qr_ids[0]}, End: {qr_ids[-1]})")

    print("\n✅ Job Card creation complete!")

if __name__ == "__main__":
    create_jobcards()
