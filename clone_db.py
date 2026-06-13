"""
clone_db.py
───────────
Clones all collections from the SOURCE MongoDB (current vega_track)
into the TARGET MongoDB (vega_track_test on the new cluster).

Run:
    venv/bin/python clone_db.py

Source : MONGO_URL in .env  →  vega_track
Target : hardcoded below     →  vega_track_test  (new cluster)
"""

import os
import sys
import logging
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

def _env(key, default=""):
    val = os.getenv(key, default).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
        val = val[1:-1]
    return val

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("clone_db")

# ── connection strings ────────────────────────────────────────────────────────
SOURCE_URL = _env("MONGO_URL", "mongodb://localhost:27017")
SOURCE_DB  = "vega_track"

TARGET_URL = "mongodb+srv://indiamotocross_db_user:w27gyGrjwcuaAlXD@cluster0.a27b75w.mongodb.net/vega_track_test?appName=Cluster0"
TARGET_DB  = "vega_track_test"

# ── connect ───────────────────────────────────────────────────────────────────
from pymongo import MongoClient, ReplaceOne
import certifi

log.info("Connecting to SOURCE: %s / %s", SOURCE_URL.split("@")[-1], SOURCE_DB)
src_client = MongoClient(SOURCE_URL, tlsCAFile=certifi.where())
src_db = src_client[SOURCE_DB]

log.info("Connecting to TARGET: %s / %s", TARGET_URL.split("@")[-1], TARGET_DB)
tgt_client = MongoClient(TARGET_URL, tlsCAFile=certifi.where())
tgt_db = tgt_client[TARGET_DB]

# ── all collections to clone ──────────────────────────────────────────────────
COLLECTIONS = [
    "users",
    "plants",
    "stations",
    "parts",
    "shifts",
    "processes",
    "reasons",
    "job_cards",
    "qr_master",
    "products",
    "scanner_processes",
    "assembly_processes",
    "dispatch_processes",
    "asset_categories",
    "asset_subcategories",
    "assets",
    "asset_assignments",
    "asset_submissions",
    "kiosks",
    "product_categories",
    "product_subcategories",
    "product_brands",
    "product_models",
    "product_submodels",
    "product_variants",
    "dealer_signup_requests",
    "b2b_inward_products",
    "b2b_cart",
    "b2b_orders",
    "b2b_coupons",
    "coin_config",
    "coin_wallets",
    "coin_transactions",
]

CHUNK_SIZE = 500   # docs per bulk_write call


def clone_collection(name: str):
    src_col = src_db[name]
    tgt_col = tgt_db[name]

    total = src_col.count_documents({})
    if total == 0:
        log.info("  %-30s  (empty — skipped)", name)
        return 0, 0

    log.info("Cloning %-30s  total=%d …", name, total)
    ok = err = 0
    batch = []

    for doc in src_col.find({}):
        # Upsert by _id so re-runs are safe (idempotent)
        batch.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))

        if len(batch) >= CHUNK_SIZE:
            try:
                tgt_col.bulk_write(batch, ordered=False)
                ok += len(batch)
            except Exception as exc:
                log.error("  %s  bulk write failed: %s", name, exc)
                err += len(batch)
            batch = []

    if batch:
        try:
            tgt_col.bulk_write(batch, ordered=False)
            ok += len(batch)
        except Exception as exc:
            log.error("  %s  final bulk write failed: %s", name, exc)
            err += len(batch)

    log.info("  %-30s  OK=%-6d  ERR=%d", name, ok, err)
    return ok, err


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 65)
    log.info("MongoDB clone:  %s  →  %s", SOURCE_DB, TARGET_DB)
    log.info("=" * 65)

    grand_ok = grand_err = 0

    for col in COLLECTIONS:
        ok, err = clone_collection(col)
        grand_ok += ok
        grand_err += err

    log.info("=" * 65)
    log.info("Clone complete ✓   Total OK=%-6d  ERR=%d", grand_ok, grand_err)
    log.info("=" * 65)
