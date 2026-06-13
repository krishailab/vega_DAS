"""
Profile each step of the job-card GET pipeline to find the bottleneck.
Run: python scratch/profile_jobcard_get.py
"""
import time, os, sys
from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
import certifi

MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

# ------------------------------------------------------------------
# Simulate what get_job_cards does for a Master Admin user
# ------------------------------------------------------------------

def timed(label, fn):
    t0 = time.perf_counter()
    result = fn()
    dt = time.perf_counter() - t0
    print(f"  {label:50s}  {dt*1000:8.1f} ms")
    return result, dt

print("=" * 72)
print("PROFILING: GET /job-cards/?page=1&limit=50")
print("=" * 72)

# Step 0: Resolve user (simulating auth)
t0_total = time.perf_counter()

user, _ = timed("0. Fetch current user (auth lookup)",
    lambda: db.users.find_one({"email": "shashi@vegaauto.com"}))

if not user:
    print("ERROR: User not found"); sys.exit(1)
print(f"     User: {user.get('first_name')} {user.get('last_name')} | role={user.get('role')} | plant_id={user.get('plant_id')}")

# Step 1: Main job_cards query
query = {}
if user.get("role") != "Super Admin":
    plant_id = user.get("plant_id")
    process_id = user.get("process_id")
    if plant_id and process_id:
        query = {"$or": [
            {"created_by": user["user_id"]},
            {"plant_id": plant_id, "process_id": process_id}
        ]}
    else:
        query["created_by"] = user["user_id"]

cards, _ = timed("1. job_cards.find(query).limit(50)",
    lambda: list(db.job_cards.find(query).limit(50)))

print(f"     → {len(cards)} cards returned")
for c in cards:
    c.pop("_id", None)

# Count total
total_count, _ = timed("1b. job_cards.count_documents(query)",
    lambda: db.job_cards.count_documents(query))
print(f"     → {total_count} total matching cards")

# --- ENRICH CARDS BATCH ---
print("\n--- _enrich_cards_batch ---")

# Creator IDs
creator_ids = list({c["created_by"] for c in cards if c.get("created_by") and (
    not c.get("created_by_name") or not c.get("created_by_role") or not c.get("created_by_department")
)})
users_map, _ = timed(f"2. users.find(user_id $in [{len(creator_ids)} ids])",
    lambda: {u["user_id"]: u for u in db.users.find(
        {"user_id": {"$in": creator_ids}},
        {"user_id": 1, "first_name": 1, "last_name": 1, "role": 1, "department": 1}
    )} if creator_ids else {})

# Variants
variant_ids = list({c["variant_id"] for c in cards if c.get("variant_id")})
variant_skus = list({c["variant_sku"] for c in cards if not c.get("variant_id") and c.get("variant_sku")})
print(f"     variant_ids={len(variant_ids)}, variant_skus={len(variant_skus)}")

variants_by_id, _ = timed(f"3a. product_variants.find(variant_id $in [{len(variant_ids)}])",
    lambda: {v["variant_id"]: v for v in db.product_variants.find({"variant_id": {"$in": variant_ids}})} if variant_ids else {})

variants_by_sku, _ = timed(f"3b. product_variants.find(sku_no $in [{len(variant_skus)}])",
    lambda: list(db.product_variants.find({"sku_no": {"$in": variant_skus}})) if variant_skus else [])

# Collect submodel_ids from variants
all_variants = {**variants_by_id}
for v in variants_by_sku:
    all_variants.setdefault(v["variant_id"], v)
submodel_ids = list({v.get("submodel_id") for v in all_variants.values() if v.get("submodel_id")})

submodels_map, _ = timed(f"4. product_submodels.find(submodel_id $in [{len(submodel_ids)}])",
    lambda: {sm["submodel_id"]: sm for sm in db.product_submodels.find({"submodel_id": {"$in": submodel_ids}})} if submodel_ids else {})

model_ids = list({sm.get("model_id") for sm in submodels_map.values() if sm.get("model_id")})
models_map, _ = timed(f"5. product_models.find(model_id $in [{len(model_ids)}])",
    lambda: {m["model_id"]: m for m in db.product_models.find({"model_id": {"$in": model_ids}})} if model_ids else {})

brand_ids = list({m.get("brand_id") for m in models_map.values() if m.get("brand_id")})
brands_map, _ = timed(f"6. product_brands.find(brand_id $in [{len(brand_ids)}])",
    lambda: {b["brand_id"]: b for b in db.product_brands.find({"brand_id": {"$in": brand_ids}})} if brand_ids else {})

# --- ENRICH COMPLETION BATCH ---
print("\n--- _enrich_completion_batch ---")

jobcard_ids = [c["jobcard_id"] for c in cards]
part_ids = list({c["part_id"] for c in cards if c.get("part_id")})

# QR master
t0_qr = time.perf_counter()
qr_docs = list(db.qr_master.find(
    {"jobcard_id": {"$in": jobcard_ids}},
    {"qr_id": 1, "jobcard_id": 1, "_id": 0}
))
dt_qr = time.perf_counter() - t0_qr
all_qr_ids = [q["qr_id"] for q in qr_docs]
print(f"  {'7. qr_master.find(jobcard_id $in [' + str(len(jobcard_ids)) + '])':50s}  {dt_qr*1000:8.1f} ms  → {len(all_qr_ids)} QR IDs")

# Processes
t0_proc = time.perf_counter()
proc_docs = list(db.processes.find({"part_id": {"$in": part_ids}}).sort("step", 1))
dt_proc = time.perf_counter() - t0_proc
print(f"  {'8. processes.find(part_id $in [' + str(len(part_ids)) + '])':50s}  {dt_proc*1000:8.1f} ms  → {len(proc_docs)} processes")

if all_qr_ids:
    # Scanner processes
    t0_scan = time.perf_counter()
    scan_docs = list(db.scanner_processes.find({"qr_id": {"$in": all_qr_ids}}))
    dt_scan = time.perf_counter() - t0_scan
    print(f"  {'9. scanner_processes.find(qr_id $in [' + str(len(all_qr_ids)) + '])':50s}  {dt_scan*1000:8.1f} ms  → {len(scan_docs)} scans")

    # Assembly processes
    t0_asm = time.perf_counter()
    asm_docs = list(db.assembly_processes.find({"component_ids": {"$in": all_qr_ids}}))
    dt_asm = time.perf_counter() - t0_asm
    print(f"  {'10. assembly_processes.find(comp_ids $in [' + str(len(all_qr_ids)) + '])':50s}  {dt_asm*1000:8.1f} ms  → {len(asm_docs)} assemblies")
else:
    print("  (no QR IDs - skipping scanner/assembly queries)")

dt_total = time.perf_counter() - t0_total
print(f"\n{'TOTAL':50s}  {dt_total*1000:8.1f} ms")
print("=" * 72)

# --- Check indexes ---
print("\n=== RELEVANT INDEXES ===")
for coll_name in ["job_cards", "qr_master", "scanner_processes", "assembly_processes",
                   "users", "product_variants", "product_submodels", "product_models",
                   "product_brands", "processes"]:
    coll = db[coll_name]
    indexes = coll.index_information()
    print(f"\n{coll_name}:")
    for idx_name, idx_info in indexes.items():
        print(f"  {idx_name}: {idx_info['key']}")

# --- Collection sizes ---
print("\n=== COLLECTION SIZES ===")
for coll_name in ["job_cards", "qr_master", "scanner_processes", "assembly_processes"]:
    cnt = db[coll_name].estimated_document_count()
    print(f"  {coll_name}: {cnt:,} documents")
