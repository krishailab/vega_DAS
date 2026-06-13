"""
check_duplicate_qr.py
─────────────────────
Diagnose duplicate qr_id records in qr_master for the two job cards.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

def _env(k, d=""):
    v = os.getenv(k, d).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1]
    return v

from pymongo import MongoClient
import certifi

client = MongoClient(_env("MONGO_URL"), tlsCAFile=certifi.where())
db = client["vega_track_test"]
qr_col = db["qr_master"]

JC1 = "JBC26AAAA0025"
JC2 = "JBC26AAAA0026"

# ── count per job card ─────────────────────────────────────────────
for jc in [JC1, JC2]:
    count = qr_col.count_documents({"jobcard_id": jc})
    print(f"\n{'='*60}")
    print(f"jobcard_id: {jc}  →  {count} qr_master records")

# ── find QR IDs that appear more than once ─────────────────────────
print(f"\n{'='*60}")
print("Checking for duplicate qr_id across both job cards …")
pipeline = [
    {"$match": {"jobcard_id": {"$in": [JC1, JC2]}}},
    {"$group": {"_id": "$qr_id", "count": {"$sum": 1}, "jobcards": {"$addToSet": "$jobcard_id"}}},
    {"$match": {"count": {"$gt": 1}}},
    {"$sort": {"_id": 1}},
]
dupes = list(qr_col.aggregate(pipeline))
print(f"Duplicate qr_ids found: {len(dupes)}")
for d in dupes[:20]:
    print(f"  qr_id={d['_id']}  count={d['count']}  jobcards={d['jobcards']}")

# ── show range counts ──────────────────────────────────────────────
print(f"\n{'='*60}")
print("qr_id count in range SA26AAA3982 → SA26AAA4224 per job card:")
for jc in [JC1, JC2]:
    docs = list(qr_col.find(
        {"jobcard_id": jc, "qr_id": {"$gte": "SA26AAA3982", "$lte": "SA26AAA4224"}},
        {"qr_id": 1, "_id": 0}
    ).sort("qr_id", 1))
    print(f"  {jc}: {len(docs)} QRs  [{docs[0]['qr_id'] if docs else 'none'} … {docs[-1]['qr_id'] if docs else 'none'}]")

print("\nDone.")
