"""
fix_duplicate_qr.py
────────────────────
Fixes 243 duplicate qr_ids (SA26AAA3982 → SA26AAA4224) shared between
JBC26AAAA0025 and JBC26AAAA0026.

Actions:
  1. JBC26AAAA0026  →  keeps the original QR IDs (no change)
  2. JBC26AAAA0025  →  each of the 243 duplicate qr_master records gets a
                       brand-new unique qr_id (next available numbers in DB)
  3. products & scanner_processes tied to JBC26AAAA0025 + old qr_id
                   →  updated to the new qr_id
  4. Firebase RTDB  →  old keys deleted, new keys written
"""

import os, sys, re, warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

def _env(k, d=""):
    v = os.getenv(k, d).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        v = v[1:-1]
    return v

import logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("fix_qr")

from pymongo import MongoClient
import certifi

# ── Connect directly to the ORIGINAL cluster (vega_track) ───────────────────
ORIG_URL = "mongodb+srv://bhagatkrish65_db_user:DGpRi6I4kDKrVLtp@cluster0.4uxyhzu.mongodb.net/?appName=Cluster0"
ORIG_DB  = "vega_track"

client = MongoClient(ORIG_URL, tlsCAFile=certifi.where())
db = client[ORIG_DB]
qr_col  = db["qr_master"]
prod_col = db["products"]
scan_col = db["scanner_processes"]

JC_KEEP = "JBC26AAAA0026"   # keeps the original QR IDs
JC_FIX  = "JBC26AAAA0025"   # will receive new unique QR IDs

DUP_START = "SA26AAA3982"
DUP_END   = "SA26AAA4224"

# ── Step 1: collect the 243 duplicate records under JBC26AAAA0025 ─────────────
dup_docs = list(qr_col.find({
    "jobcard_id": JC_FIX,
    "qr_id": {"$gte": DUP_START, "$lte": DUP_END}
}).sort("qr_id", 1))

log.info("Found %d duplicate qr_master docs under %s to reassign.", len(dup_docs), JC_FIX)
if not dup_docs:
    log.error("Nothing to do — exiting.")
    sys.exit(0)

# ── Step 2: find prefix + max numeric suffix across ALL qr_ids in DB ──────────
log.info("Scanning all qr_ids to find max numeric suffix …")

all_qr_ids = [d["qr_id"] for d in qr_col.find({}, {"qr_id": 1, "_id": 0})]

# Extract (prefix, number) from each qr_id  e.g. "SA26AAA3982" → ("SA26AAA", 3982)
pattern = re.compile(r'^([A-Za-z]+\d*[A-Za-z]*)(\d+)$')

prefix_max: dict[str, int] = {}
for qid in all_qr_ids:
    m = pattern.match(qid)
    if m:
        pre, num = m.group(1), int(m.group(2))
        if pre not in prefix_max or num > prefix_max[pre]:
            prefix_max[pre] = num

log.info("Prefix → max number found: %s", prefix_max)

# Determine prefix from the duplicate range
sample_m = pattern.match(DUP_START)
if not sample_m:
    log.error("Cannot parse prefix from %s", DUP_START)
    sys.exit(1)

PREFIX = sample_m.group(1)        # e.g. "SA26AAA"
NUM_WIDTH = len(sample_m.group(2))  # e.g. 4  (zero-pad width)
current_max = prefix_max.get(PREFIX, 0)
log.info("Will generate new IDs with prefix='%s', starting after %d (width=%d)",
         PREFIX, current_max, NUM_WIDTH)

# ── Step 3: generate 243 new unique qr_ids ────────────────────────────────────
existing_set = set(all_qr_ids)
new_ids = []
counter = current_max + 1
while len(new_ids) < len(dup_docs):
    candidate = f"{PREFIX}{str(counter).zfill(NUM_WIDTH)}"
    if candidate not in existing_set:
        new_ids.append(candidate)
        existing_set.add(candidate)  # prevent re-use within this run
    counter += 1

log.info("Generated %d new qr_ids: %s … %s", len(new_ids), new_ids[0], new_ids[-1])

# ── Step 4: build old→new mapping ─────────────────────────────────────────────
mapping = {doc["qr_id"]: new_id for doc, new_id in zip(dup_docs, new_ids)}

# ── Step 5: update qr_master ──────────────────────────────────────────────────
log.info("Updating qr_master …")
qr_ok = qr_err = 0
for old_id, new_id in mapping.items():
    try:
        qr_col.update_one(
            {"jobcard_id": JC_FIX, "qr_id": old_id},
            {"$set": {"qr_id": new_id}}
        )
        qr_ok += 1
    except Exception as e:
        log.error("  qr_master  %s → %s  FAILED: %s", old_id, new_id, e)
        qr_err += 1
log.info("  qr_master  OK=%d  ERR=%d", qr_ok, qr_err)

# ── Step 6: update products ───────────────────────────────────────────────────
log.info("Updating products …")
prod_ok = prod_err = prod_skip = 0
for old_id, new_id in mapping.items():
    res = prod_col.update_many(
        {"jobcard_id": JC_FIX, "qr_id": old_id},
        {"$set": {"qr_id": new_id}}
    )
    if res.matched_count:
        prod_ok += res.matched_count
    else:
        prod_skip += 1
log.info("  products  updated=%d  not_found=%d  ERR=%d", prod_ok, prod_skip, prod_err)

# ── Step 7: update scanner_processes ─────────────────────────────────────────
log.info("Updating scanner_processes …")
scan_ok = scan_err = scan_skip = 0
for old_id, new_id in mapping.items():
    res = scan_col.update_many(
        {"jobcard_id": JC_FIX, "qr_id": old_id},
        {"$set": {"qr_id": new_id}}
    )
    if res.matched_count:
        scan_ok += res.matched_count
    else:
        scan_skip += 1
log.info("  scanner_processes  updated=%d  not_found=%d  ERR=%d", scan_ok, scan_skip, scan_err)

# ── Step 8: sync to Firebase RTDB ────────────────────────────────────────────
try:
    from app.firebase_client import init_firebase, delete_from_rtdb, sync_qr_master, sync_product, sync_scan
    init_firebase()

    log.info("Updating Firebase RTDB …")
    fb_ok = 0

    # qr_master: remove old keys, write new
    for old_id, new_id in mapping.items():
        delete_from_rtdb(f"/qr_master/{old_id}")

    # Write updated qr_master docs
    for doc in qr_col.find({"jobcard_id": JC_FIX, "qr_id": {"$in": new_ids}}):
        sync_qr_master(dict(doc))
        fb_ok += 1

    # products
    for old_id, new_id in mapping.items():
        delete_from_rtdb(f"/products/{old_id}")
    for doc in prod_col.find({"jobcard_id": JC_FIX, "qr_id": {"$in": new_ids}}):
        sync_product(dict(doc))

    # scanner_processes (keyed by scan_id, but qr_id field updated)
    for doc in scan_col.find({"jobcard_id": JC_FIX, "qr_id": {"$in": new_ids}}):
        sync_scan(dict(doc))

    log.info("  Firebase sync done  qr_master=%d", fb_ok)
except Exception as e:
    log.warning("Firebase sync skipped: %s", e)

# ── Summary ───────────────────────────────────────────────────────────────────
log.info("=" * 65)
log.info("Fix complete.")
log.info("  %s  keeps  %s … %s  (%d QRs)", JC_KEEP, DUP_START, DUP_END, len(dup_docs))
log.info("  %s  now has  %s … %s  (%d NEW QRs)", JC_FIX, new_ids[0], new_ids[-1], len(new_ids))
log.info("=" * 65)
