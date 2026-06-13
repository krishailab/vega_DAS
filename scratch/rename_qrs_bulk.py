import sys
import os

# Add the workspace root to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, qr_master_collection, scanner_processes_collection
from app.firebase_client import init_firebase, delete_from_rtdb, set_to_rtdb, escape_firebase_key
from pymongo import UpdateOne

def rename_qrs_bulk():
    init_firebase()
    
    jobcard_id = "JBC26A0096"
    prefix = "062090/P-"
    
    print("Fetching remaining QR codes with prefix...")
    qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id, "qr_id": {"$regex": f"^{prefix}"}}))
    print(f"Found {len(qrs)} QR codes to rename.")
    
    if not qrs:
        print("No QR codes found with the prefix.")
        return
        
    # 1. Bulk Update qr_master in MongoDB
    print("Performing bulk update on qr_master in MongoDB...")
    qr_ops = []
    for qr in qrs:
        old_id = qr["qr_id"]
        new_id = old_id.replace(prefix, "")
        qr_ops.append(UpdateOne({"_id": qr["_id"]}, {"$set": {"qr_id": new_id}}))
        
    if qr_ops:
        res = qr_master_collection.bulk_write(qr_ops)
        print(f"qr_master bulk update completed. Modified: {res.modified_count}")
        
    # 2. Bulk Update scanner_processes in MongoDB
    print("Performing bulk update on scanner_processes in MongoDB...")
    scan_res = scanner_processes_collection.update_many(
        {"qr_id": {"$regex": f"^{prefix}"}},
        [{"$set": {"qr_id": {"$replaceAll": {"input": "$qr_id", "find": prefix, "replacement": ""}}}}]
    )
    print(f"scanner_processes bulk update completed. Modified: {scan_res.modified_count}")
    
    # 3. Firebase Updates (Optional/Asynchronous background tasks)
    print("Queuing Firebase RTDB updates in background threads...")
    for idx, qr in enumerate(qrs):
        old_id = qr["qr_id"]
        new_id = old_id.replace(prefix, "")
        
        # Delete old key
        delete_from_rtdb(f"/qr_master/{escape_firebase_key(old_id)}")
        
        # Set new key
        new_qr_doc = dict(qr)
        new_qr_doc.pop("_id", None)
        new_qr_doc["qr_id"] = new_id
        set_to_rtdb(f"/qr_master/{escape_firebase_key(new_id)}", new_qr_doc)
        
        if (idx + 1) % 1000 == 0:
            print(f"Queued {idx + 1}/{len(qrs)} Firebase updates...")
            
    print("\nBulk migration script finished!")
    print("MongoDB updates are fully saved. Firebase updates are processing in the background.")

if __name__ == "__main__":
    rename_qrs_bulk()
