import sys
import os

# Add the workspace root to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, qr_master_collection, scanner_processes_collection
from app.firebase_client import init_firebase, delete_from_rtdb, set_to_rtdb, escape_firebase_key

def rename_qrs():
    init_firebase()
    
    jobcard_id = "JBC26A0096"
    prefix = "062090/P-"
    
    print(f"Finding QR codes for job card: {jobcard_id} with prefix: {prefix}")
    
    qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id}))
    print(f"Found {len(qrs)} QR codes.")
    
    renamed_count = 0
    scans_updated_count = 0
    
    for idx, qr in enumerate(qrs):
        old_qr_id = qr.get("qr_id")
        if old_qr_id and old_qr_id.startswith(prefix):
            new_qr_id = old_qr_id.replace(prefix, "")
            
            # 1. Update scanner_processes in MongoDB & retrieve scan documents for Firebase update
            scans = list(scanner_processes_collection.find({"qr_id": old_qr_id}))
            if scans:
                scanner_processes_collection.update_many({"qr_id": old_qr_id}, {"$set": {"qr_id": new_qr_id}})
                scans_updated_count += len(scans)
            
            # 2. Update qr_master in MongoDB
            qr_master_collection.update_one({"_id": qr["_id"]}, {"$set": {"qr_id": new_qr_id}})
            renamed_count += 1
            
            # 3. Sync changes to Firebase
            # Delete old qr_master entry
            delete_from_rtdb(f"/qr_master/{escape_firebase_key(old_qr_id)}")
            # Write new qr_master entry
            new_qr_doc = dict(qr)
            new_qr_doc.pop("_id", None)
            new_qr_doc["qr_id"] = new_qr_id
            set_to_rtdb(f"/qr_master/{escape_firebase_key(new_qr_id)}", new_qr_doc)
            
            # Update scan processes in Firebase
            for scan in scans:
                scan_id = scan.get("scan_id")
                if scan_id:
                    new_scan_doc = dict(scan)
                    new_scan_doc.pop("_id", None)
                    new_scan_doc["qr_id"] = new_qr_id
                    set_to_rtdb(f"/scanner_processes/{scan_id}", new_scan_doc)
            
            if renamed_count % 100 == 0:
                print(f"Processed {renamed_count}/{len(qrs)} QR codes...")
                
    print(f"\nMigration Completed!")
    print(f"Total QR codes renamed in MongoDB & Firebase: {renamed_count}")
    print(f"Total Scanner processes updated: {scans_updated_count}")

if __name__ == "__main__":
    rename_qrs()
