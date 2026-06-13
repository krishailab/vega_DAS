import sys
import os

# Add the workspace root to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, qr_master_collection

def query():
    jobcard_id = "JBC26A0096"
    qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id}).limit(10))
    print(f"Found {qr_master_collection.count_documents({'jobcard_id': jobcard_id})} QRs total.")
    for q in qrs:
        print(q.get("qr_id"))

if __name__ == "__main__":
    query()
