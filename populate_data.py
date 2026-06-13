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

def populate_data():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    processes_col = db["processes"]
    stations_col = db["stations"]
    
    # 1. Identify Master Admins
    master_admins = list(users_col.find({"role": "Master Admin"}))
    if not master_admins:
        print("No Master Admins found in the database. Please run init_master_admins.py first.")
        return
        
    print(f"Found {len(master_admins)} Master Admins.")
    
    # 2. For each Master Admin, create 4 processes and 4 stations per process
    process_base_names = ["Moulding", "Coating", "Assembly", "Inspection"]
    
    for admin in master_admins:
        admin_id = admin["user_id"]
        admin_name = admin["first_name"]
        print(f"\nProcessing Master Admin: {admin_name} ({admin_id})")
        
        for i in range(4):
            process_name = f"{admin_name} {process_base_names[i]}"
            
            # Check if process exists
            existing_process = processes_col.find_one({"name": process_name, "created_by": admin_id})
            if not existing_process:
                process_id = generate_custom_id("PRO", processes_col, "process_id")
                process_doc = {
                    "process_id": process_id,
                    "name": process_name,
                    "created_by": admin_id,
                    "created_at": get_current_time()
                }
                processes_col.insert_one(process_doc)
                print(f"  Created Process: {process_name} ({process_id})")
            else:
                process_id = existing_process["process_id"]
                print(f"  Process exists: {process_name} ({process_id})")
            
            # Create 4 stations for this process
            for j in range(1, 5):
                station_name = f"{process_name} - Station {j}"
                
                # Check if station exists
                existing_station = stations_col.find_one({"name": station_name, "master_admin_id": admin_id})
                if not existing_station:
                    stn_id = generate_custom_id("STN", stations_col, "station_id")
                    station_doc = {
                        "station_id": stn_id,
                        "name": station_name,
                        "process": process_name,
                        "master_admin_id": admin_id,
                        "active": True
                    }
                    stations_col.insert_one(station_doc)
                    print(f"    Created Station: {station_name} ({stn_id})")
                else:
                    print(f"    Station exists: {station_name}")

    print("\n✅ Data population complete!")

if __name__ == "__main__":
    populate_data()
