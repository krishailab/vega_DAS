"""
Migration: Backfill product_model_name into existing job_cards (no variant linkage)

Mapping:
  part_model == "SHELL"  ->  product_model_name = "APEX-2"
  part_model == "LINER"  ->  product_model_name = "X-CROSS"
"""

import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

job_cards_col = db["job_cards"]

# Mapping: part_model -> product_model_name
PART_MODEL_MAP = {
    "SHELL": "APEX-2",
    "LINER": "X-CROSS",
}

print("Starting migration: backfill product_model_name in job_cards...\n")

updated = 0
skipped = 0
unresolved = 0

for jc in job_cards_col.find({}):
    jc_id = jc.get("jobcard_id", str(jc["_id"]))

    # Rename existing model_name (old wrong field) -> product_model_name if needed
    if jc.get("product_model_name"):
        skipped += 1
        continue

    # If old model_name exists (from previous migration run), move it to product_model_name
    old_val = jc.get("model_name")
    if old_val and old_val in ("APEX-2", "X-CROSS"):
        job_cards_col.update_one(
            {"_id": jc["_id"]},
            {
                "$set": {"product_model_name": old_val},
                "$unset": {"model_name": ""}
            }
        )
        print(f"  Moved {jc_id}: model_name -> product_model_name: {old_val}")
        updated += 1
        continue

    part_model = jc.get("part_model", "").strip().upper()
    model_name = PART_MODEL_MAP.get(part_model)

    if not model_name:
        print(f"  SKIP (unresolved) {jc_id} — part_model: '{jc.get('part_model')}'")
        unresolved += 1
        continue

    job_cards_col.update_one(
        {"_id": jc["_id"]},
        {"$set": {"product_model_name": model_name}}
    )
    print(f"  Updated {jc_id} (part_model={jc.get('part_model')}) -> product_model_name: {model_name}")
    updated += 1

print(f"\nMigration complete!")
print(f"  Updated   : {updated}")
print(f"  Skipped   : {skipped} (already had product_model_name)")
print(f"  Unresolved: {unresolved} (no mapping found)")
