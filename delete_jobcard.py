import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, job_cards_collection, qr_master_collection, scanner_processes_collection

def delete_jobcard():
    jobcard_no = "JBC26A0063"
    print(f"=== Deleting Job Card: {jobcard_no} ===")
    job_card = job_cards_collection.find_one({"jobcard_no": jobcard_no})
    if not job_card:
        job_card = job_cards_collection.find_one({"jobcard_id": jobcard_no})
        
    if not job_card:
        print("Job card not found!")
        return
        
    jobcard_id = job_card.get("jobcard_id")
    qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id}))
    
    qr_ids = [qr.get("qr_id") for qr in qrs if qr.get("qr_id")]
    print(f"Found {len(qr_ids)} associated QR codes.")
    scans_deleted = 0
    if qr_ids:
        del_scans_res = scanner_processes_collection.delete_many({"qr_id": {"$in": qr_ids}})
        scans_deleted = del_scans_res.deleted_count
    print(f"Deleted {scans_deleted} scanner processes.")
    qrs_deleted = 0
    if qr_ids:
        del_qrs_res = qr_master_collection.delete_many({"jobcard_id": jobcard_id})
        qrs_deleted = del_qrs_res.deleted_count
    print(f"Deleted {qrs_deleted} QR codes from qr_master.")
    del_jb_res = job_cards_collection.delete_one({"_id": job_card["_id"]})
    print(f"Deleted job card document. Success: {del_jb_res.deleted_count > 0}")
    
    print("\nDeletion finished successfully!")

if __name__ == "__main__":
    delete_jobcard()
