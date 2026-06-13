import time, os
from dotenv import load_dotenv
load_dotenv()
from pymongo import MongoClient
import certifi

MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

job_cards = list(db.job_cards.find({}).limit(50))
jobcard_ids = [c["jobcard_id"] for c in job_cards]

print(f"Testing group-by count aggregation for {len(jobcard_ids)} jobcards...")

t0 = time.perf_counter()

# Aggregate scans
scan_pipeline = [
    # Join with qr_master
    {"$lookup": {
        "from": "qr_master",
        "localField": "qr_id",
        "foreignField": "qr_id",
        "as": "qr_info"
    }},
    {"$unwind": "$qr_info"},
    {"$match": {"qr_info.jobcard_id": {"$in": jobcard_ids}}},
    {"$group": {
        "_id": {
            "jobcard_id": "$qr_info.jobcard_id",
            "process_name": "$process_name"
        },
        "unique_qrs": {"$addToSet": "$qr_id"}
    }}
]
scan_results = list(db.scanner_processes.aggregate(scan_pipeline))

# Aggregate assemblies
asm_pipeline = [
    # Join with qr_master
    {"$lookup": {
        "from": "qr_master",
        "localField": "component_ids",
        "foreignField": "qr_id",
        "as": "qr_info"
    }},
    {"$unwind": "$qr_info"},
    {"$match": {"qr_info.jobcard_id": {"$in": jobcard_ids}}},
    {"$group": {
        "_id": {
            "jobcard_id": "$qr_info.jobcard_id",
            "process_name": "$process_name"
        },
        "unique_qrs": {"$addToSet": "$qr_info.qr_id"}
    }}
]
asm_results = list(db.assembly_processes.aggregate(asm_pipeline))

# Merge counts in Python
completed_qrs = {} # { (jobcard_id, process_name): set(qr_ids) }
for r in scan_results:
    key = (r["_id"]["jobcard_id"], r["_id"]["process_name"])
    completed_qrs.setdefault(key, set()).update(r["unique_qrs"])

for r in asm_results:
    key = (r["_id"]["jobcard_id"], r["_id"]["process_name"])
    completed_qrs.setdefault(key, set()).update(r["unique_qrs"])

dt = time.perf_counter() - t0
print(f"Time: {dt*1000:.1f} ms")
print(f"Computed unique completed QR sets for {len(completed_qrs)} jobcard-process pairs")

# Print first few counts
for (jc_id, p_name), qrs in list(completed_qrs.items())[:5]:
    print(f"  JobCard: {jc_id} | Process: {p_name} | Completed Count: {len(qrs)}")
