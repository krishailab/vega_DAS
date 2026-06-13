#!/usr/bin/env python3
"""
Migration: Migrate Station IDs to the single-letter format (e.g. STN26A0001)
========================================================================
This script updates existing station records in MongoDB:
1. Translates old station IDs (e.g. STN26AA0001, STN26AAAA0001) to the new format (STN26A0001).
2. Regenerates/updates the QR code image path.
3. Propagates the changes to all referencing collections:
   - users (assigned_station_id)
   - scanner_processes (station_id)
   - assembly_processes (station_id)
   - dispatch_processes (station_id)
   - job_cards (station_ids array)

Usage:
    PYTHONPATH=. venv/bin/python3 scripts/migrate_station_ids.py
"""

import os
import re
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from app.utils import generate_qr_file

load_dotenv()

def convert_station_id(old_id: str) -> str:
    if not old_id:
        return old_id
        
    # Match pattern e.g., STN26AAAA0001 or STN26AA0001
    match = re.match(r"^STN(\d{2})([A-Z]+)(\d+)$", old_id)
    if not match:
        return old_id
        
    yy = match.group(1)
    letters = match.group(2)
    digits_str = match.group(3)
    
    count = int(digits_str)
    
    if len(letters) == 4:
        c1, c2, c3, c4 = letters
        xx_index = (ord(c1) - 65) * 26**3 + (ord(c2) - 65) * 26**2 + (ord(c3) - 65) * 26 + (ord(c4) - 65)
    elif len(letters) == 2:
        c1, c2 = letters
        xx_index = (ord(c1) - 65) * 26 + (ord(c2) - 65)
    elif len(letters) == 1:
        return old_id
    else:
        xx_index = 0
        
    count_this_year = xx_index * 9999 + (count - 1)
    
    new_xx_index = count_this_year // 9999
    new_count = (count_this_year % 9999) + 1
    new_char = chr(65 + new_xx_index % 26)
    
    return f"STN{yy}{new_char}{new_count:04d}"

def migrate():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    stations_col = db["stations"]
    users_col = db["users"]
    scanner_processes_col = db["scanner_processes"]
    assembly_processes_col = db["assembly_processes"]
    dispatch_processes_col = db["dispatch_processes"]
    job_cards_col = db["job_cards"]
    
    stations = list(stations_col.find({}))
    print(f"Found {len(stations)} total stations in database.")
    
    migrated_count = 0
    
    for station in stations:
        old_id = station.get("station_id")
        if not old_id:
            continue
            
        new_id = convert_station_id(old_id)
        if old_id == new_id:
            print(f"Station {old_id} is already in the correct format. Skipping.")
            continue
            
        print(f"Migrating station: {old_id} -> {new_id}")
        
        # 1. Update Stations collection
        # Regenerate QR code for the new station ID
        master_admin_id = station.get("master_admin_id", "SYSTEM")
        new_qr_path = generate_qr_file(new_id, master_admin_id, "Station", new_id)
        
        stations_col.update_one(
            {"_id": station["_id"]},
            {"$set": {
                "station_id": new_id,
                "qrcode": new_qr_path
            }}
        )
        
        # 2. Update Users collection (assigned_station_id)
        u_res = users_col.update_many(
            {"assigned_station_id": old_id},
            {"$set": {"assigned_station_id": new_id}}
        )
        if u_res.modified_count > 0:
            print(f"  -> Updated {u_res.modified_count} users")
            
        # 3. Update scanner_processes collection
        sp_res = scanner_processes_col.update_many(
            {"station_id": old_id},
            {"$set": {"station_id": new_id}}
        )
        if sp_res.modified_count > 0:
            print(f"  -> Updated {sp_res.modified_count} scanner processes")
            
        # 4. Update assembly_processes collection
        ap_res = assembly_processes_col.update_many(
            {"station_id": old_id},
            {"$set": {"station_id": new_id}}
        )
        if ap_res.modified_count > 0:
            print(f"  -> Updated {ap_res.modified_count} assembly processes")
            
        # 5. Update dispatch_processes collection
        dp_res = dispatch_processes_col.update_many(
            {"station_id": old_id},
            {"$set": {"station_id": new_id}}
        )
        if dp_res.modified_count > 0:
            print(f"  -> Updated {dp_res.modified_count} dispatch processes")
            
        # 6. Update job_cards collection (station_ids array)
        jc_res = job_cards_col.update_many(
            {"station_ids": old_id},
            {"$set": {"station_ids.$": new_id}}
        )
        if jc_res.modified_count > 0:
            print(f"  -> Updated {jc_res.modified_count} job cards")
            
        migrated_count += 1
        
    print(f"\nMigration finished. Total stations migrated: {migrated_count}")

if __name__ == "__main__":
    migrate()
