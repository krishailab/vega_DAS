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
    
    if prefix == "STN":
        c = chr(65 + xx_index % 26)
        return f"{prefix}{yy}{c}{count:04d}"
        
    first_char = chr(65 + (xx_index // 26))
    second_char = chr(65 + (xx_index % 26))
    
    return f"{prefix}{yy}{first_char}{second_char}{count:04d}"

def init_stations():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    stations_col = db["stations"]
    processes_col = db["processes"]
    users_col = db["users"]
    
    # 1. Define 4 Processes
    processes_list = [
        "Molding",
        "Painting",
        "Final Assembly",
        "Quality Inspection"
    ]
    
    process_ids = {}
    for p_name in processes_list:
        existing = processes_col.find_one({"name": p_name})
        if existing:
            process_ids[p_name] = existing["process_id"]
            print(f"Process {p_name} already exists.")
        else:
            p_id = generate_custom_id("PRO", processes_col, "process_id")
            processes_col.insert_one({
                "process_id": p_id,
                "name": p_name,
                "created_by": "SYSTEM",
                "created_at": get_current_time()
            })
            process_ids[p_name] = p_id
            print(f"Created Process: {p_name} ({p_id})")

    # 2. Get Master Admins
    master_admins = list(users_col.find({"role": "Master Admin"}))
    if not master_admins:
        print("No Master Admins found. Run init_master_admins.py first.")
        return

    # 3. Create 4 Stations for each Master Admin (one for each process)
    for admin in master_admins:
        admin_id = admin["user_id"]
        admin_name = admin["first_name"]
        
        print(f"\nProcessing Master Admin: {admin_name} ({admin_id})")
        
        for p_name in processes_list:
            # Check if station already exists for this admin and process
            station_name = f"{admin_name} {p_name} Station"
            existing = stations_col.find_one({
                "master_admin_id": admin_id,
                "process": p_name
            })
            
            if existing:
                print(f"Station {station_name} already exists.")
            else:
                s_id = generate_custom_id("STN", stations_col, "station_id")
                stations_col.insert_one({
                    "station_id": s_id,
                    "name": station_name,
                    "process": p_name,
                    "active": True,
                    "master_admin_id": admin_id,
                    "created_at": get_current_time()
                })
                print(f"Created Station: {station_name} ({s_id})")

    print("\n✅ Station initialization complete!")

if __name__ == "__main__":
    init_stations()
