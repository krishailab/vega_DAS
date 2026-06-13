import sys
import os
import json

# Add the workspace root to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, job_cards_collection, qr_master_collection, scanner_processes_collection

def query_details():
    jobcard_no = "JBC26A0067"
    print(f"=== Querying Job Card: {jobcard_no} ===")
    
    # 1. Get Job Card details
    job_card = job_cards_collection.find_one({"jobcard_no": jobcard_no})
    if not job_card:
        job_card = job_cards_collection.find_one({"jobcard_id": jobcard_no})
        
    if not job_card:
        print("Job card not found!")
        return
        
    def clean_doc(doc):
        if not doc:
            return None
        doc = dict(doc)
        doc.pop("_id", None)
        for k, v in doc.items():
            if hasattr(v, "isoformat"):
                doc[k] = v.isoformat()
        return doc

    print("\n--- JOB CARD DOC ---")
    print(json.dumps(clean_doc(job_card), indent=2))
    
    jobcard_id = job_card.get("jobcard_id")
    
    # 2. Find associated QRs in qr_master
    qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id}))
    print(f"\n--- QR MASTER SUMMARY ---")
    print(f"Total QR Codes associated: {len(qrs)}")
    if qrs:
        print(f"First 5 QRs:")
        for qr in qrs[:5]:
            print(f"  - QR ID: {qr.get('qr_id')} | Status: {qr.get('status')}")
        print(f"Last 5 QRs:")
        for qr in qrs[-5:]:
            print(f"  - QR ID: {qr.get('qr_id')} | Status: {qr.get('status')}")
        
    qr_ids = [qr.get("qr_id") for qr in qrs if qr.get("qr_id")]
    if not qr_ids:
        print("No QR IDs found for this job card.")
        return
        
    # 3. Find scan processes for these QRs
    scans = list(scanner_processes_collection.find({"qr_id": {"$in": qr_ids}}))
    print(f"\n--- SCAN PROCESSES SUMMARY ---")
    print(f"Total Scan Processes: {len(scans)}")
    if scans:
        # Sort scans by start_time
        scans.sort(key=lambda s: s.get("start_time") or "")
        print(f"First 5 Scan processes:")
        for scan in scans[:5]:
            print(f"  - Scan ID: {scan.get('scan_id')} | QR: {scan.get('qr_id')} | Station: {scan.get('station_name')} | Status: {scan.get('inspection_status')} | Time: {scan.get('start_time')}")
        print(f"Last 5 Scan processes:")
        for scan in scans[-5:]:
            print(f"  - Scan ID: {scan.get('scan_id')} | QR: {scan.get('qr_id')} | Station: {scan.get('station_name')} | Status: {scan.get('inspection_status')} | Time: {scan.get('start_time')}")

if __name__ == "__main__":
    query_details()
