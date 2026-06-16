"""
Cleanup script — deletes a jobcard and ALL associated data:
  - job_cards
  - qr_master
  - scanner_processes
  - assembly_processes (component_ids / qr_ids)
  - products
  - Firebase RTDB nodes

Usage:
    python cleanup_jobcard.py JBC26A0160
    python cleanup_jobcard.py JBC26A0160 JBC26A0159   # multiple
"""

import sys
from app.database import (
    job_cards_collection,
    qr_master_collection,
    scanner_processes_collection,
    products_collection,
)
try:
    from app.database import assembly_processes_collection
except ImportError:
    assembly_processes_collection = None

from app.firebase_client import delete_from_rtdb, escape_firebase_key

JOBCARD_IDS = sys.argv[1:] or ["JBC26A0160"]

def cleanup(jobcard_id: str):
    print(f"\n{'='*60}")
    print(f"Cleaning up jobcard: {jobcard_id}")
    print(f"{'='*60}")

    # 1. Fetch jobcard
    jc = job_cards_collection.find_one({"jobcard_id": jobcard_id})
    if not jc:
        print(f"  ⚠  Jobcard {jobcard_id} not found — skipping.")
        return

    # 2. Collect all owned QR IDs
    qr_docs = list(qr_master_collection.find({"jobcard_id": jobcard_id}, {"qr_id": 1}))
    qr_ids = [q["qr_id"] for q in qr_docs if q.get("qr_id")]
    print(f"  Found {len(qr_ids)} QR(s): {qr_ids}")

    # 3. Delete scanner_processes for these QRs
    if qr_ids:
        res = scanner_processes_collection.delete_many({"qr_id": {"$in": qr_ids}})
        print(f"  Deleted {res.deleted_count} scanner_process record(s)")

    # 4. Delete assembly_processes that reference these QRs
    if assembly_processes_collection is not None and qr_ids:
        res1 = assembly_processes_collection.delete_many({"component_ids": {"$in": qr_ids}})
        res2 = assembly_processes_collection.delete_many({"qr_ids": {"$in": qr_ids}})
        print(f"  Deleted {res1.deleted_count + res2.deleted_count} assembly_process record(s)")

    # 5. Delete products
    if qr_ids:
        res = products_collection.delete_many({"qr_id": {"$in": qr_ids}})
        print(f"  Deleted {res.deleted_count} product record(s)")

    # 6. Delete qr_master records
    if qr_ids:
        res = qr_master_collection.delete_many({"jobcard_id": jobcard_id})
        print(f"  Deleted {res.deleted_count} qr_master record(s)")

    # 7. Delete the jobcard itself
    job_cards_collection.delete_one({"jobcard_id": jobcard_id})
    print(f"  Deleted jobcard document")

    # 8. Firebase cleanup
    print(f"  Cleaning Firebase...")
    try:
        delete_from_rtdb(f"/job_cards/{jobcard_id}")
        print(f"    /job_cards/{jobcard_id} ✓")
        for qr_id in qr_ids:
            key = escape_firebase_key(qr_id)
            delete_from_rtdb(f"/qr_master/{key}")
        print(f"    /qr_master/* ({len(qr_ids)} nodes) ✓")
    except Exception as e:
        print(f"    Firebase error (non-fatal): {e}")

    print(f"  ✅ Done: {jobcard_id}")


if __name__ == "__main__":
    for jid in JOBCARD_IDS:
        cleanup(jid.strip())
    print("\n✅ All cleanup complete.")
