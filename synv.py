"""
sync_to_firebase.py
───────────────────
Full sync: clones the current state of all core MongoDB collections into
Firebase Realtime Database, using the **same RTDB path layout** that the
live API uses (via firebase_client.py).

Collections synced
──────────────────
  MongoDB              →  RTDB path
  ─────────────────────────────────
  job_cards            →  /job_cards/{jobcard_id}
  qr_master            →  /qr_master/{qr_id}
  products             →  /products/{qr_id}
  scanner_processes    →  /scanner_processes/{scan_id}
  assembly_processes   →  /assembly_processes/{assembly_id}
  dispatch_processes   →  /dispatch_processes/{dispatch_id}

Run from the project root:
    python -m scripts.sync_to_firebase
    python scripts/sync_to_firebase.py

.env requirements:
    MONGO_URL=<mongo connection string>
    FIREBASE_DATABASE_URL=https://<project>-default-rtdb.firebaseio.com
    FIREBASE_SERVICE_ACCOUNT=/path/to/service-account.json  (or raw JSON string)
"""

import os
import sys
import json
import logging
from datetime import datetime, date
import warnings

# ── suppress noisy 3rd-party warnings ────────────────────────────────────────
warnings.filterwarnings("ignore", category=FutureWarning, module="google.auth")
warnings.filterwarnings("ignore", category=FutureWarning, module="google.oauth2")
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

# synv.py lives at the project root — .env is in the same directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _env(key: str, default: str = "") -> str:
    """Get env var, stripping surrounding quotes that dotenv may preserve."""
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
log = logging.getLogger("sync_firebase")

# ── MongoDB ───────────────────────────────────────────────────────────────────
from pymongo import MongoClient
import certifi

MONGO_URL = _env("MONGO_URL", "mongodb://localhost:27017")
mongo_client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())

# Always use vega_track — same as app/database.py
db = mongo_client["vega_track"]

job_cards_col     = db["job_cards"]
qr_master_col     = db["qr_master"]
products_col      = db["products"]
scanner_col       = db["scanner_processes"]
assembly_col      = db["assembly_processes"]
dispatch_col      = db["dispatch_processes"]

# ── Firebase Admin SDK ────────────────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, db as firebase_db

DATABASE_URL        = _env("FIREBASE_DATABASE_URL")
SERVICE_ACCOUNT_RAW = _env("FIREBASE_SERVICE_ACCOUNT")

if not DATABASE_URL:
    log.error("FIREBASE_DATABASE_URL is not set in .env — aborting.")
    sys.exit(1)
if not SERVICE_ACCOUNT_RAW:
    log.error("FIREBASE_SERVICE_ACCOUNT is not set in .env — aborting.")
    sys.exit(1)

# Accept file path OR raw JSON string
if SERVICE_ACCOUNT_RAW.startswith("{"):
    cred = credentials.Certificate(json.loads(SERVICE_ACCOUNT_RAW))
else:
    if not os.path.exists(SERVICE_ACCOUNT_RAW):
        log.error("Service-account file not found: %s", SERVICE_ACCOUNT_RAW)
        sys.exit(1)
    cred = credentials.Certificate(SERVICE_ACCOUNT_RAW)

firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
log.info("Firebase Admin SDK initialised ✓  →  %s", DATABASE_URL)


# ── helpers ───────────────────────────────────────────────────────────────────
def _safe(v):
    """Recursively convert non-JSON-serialisable types."""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, list):
        return [_safe(i) for i in v]
    if isinstance(v, dict):
        return {k: _safe(val) for k, val in v.items()}
    # bson ObjectId and similar exotic types
    if not isinstance(v, (str, int, float, bool, type(None))):
        return str(v)
    return v


def _sanitise(doc: dict) -> dict:
    """Strip MongoDB _id and serialize datetimes."""
    return {k: _safe(v) for k, v in doc.items() if k != "_id"}


def _safe_key(s) -> str:
    """Firebase keys must not contain . # $ [ ]"""
    return str(s).replace(".", "_").replace("#", "_").replace("$", "_") \
                 .replace("[", "_").replace("]", "_")


CHUNK_SIZE = 500   # records per Firebase batch-update call

def _batch_set(collection, id_field: str, rtdb_root: str, label: str):
    """
    Batch-write all docs in *collection* to /{rtdb_root}/ using Firebase
    update() in chunks of CHUNK_SIZE — far fewer HTTP round-trips than
    one set() per document.
    """
    total = collection.count_documents({})
    log.info("Syncing %-28s  total=%d …", label, total)
    ok = err = 0
    chunk = {}

    def _flush(chunk: dict):
        nonlocal ok, err
        if not chunk:
            return
        try:
            firebase_db.reference(f"/{rtdb_root}").update(chunk)
            ok += len(chunk)
        except Exception as exc:
            log.error("  %s  batch flush failed: %s", label, exc)
            err += len(chunk)

    for doc in collection.find({}):
        doc_id = doc.get(id_field)
        if not doc_id:
            log.warning("  %s: missing '%s' — skipped", label, id_field)
            continue
        safe_id = _safe_key(doc_id)
        chunk[safe_id] = _sanitise(doc)

        if len(chunk) >= CHUNK_SIZE:
            _flush(chunk)
            log.info("  %s  … %d written so far", label, ok)
            chunk = {}

    _flush(chunk)   # remaining records
    log.info("  %-28s  OK=%-5d  ERR=%d", label, ok, err)
    return ok, err


# ── individual collection syncs ───────────────────────────────────────────────
def sync_job_cards():
    _batch_set(job_cards_col, "jobcard_id", "job_cards", "job_cards")


def sync_qr_master():
    _batch_set(qr_master_col, "qr_id", "qr_master", "qr_master")


def sync_products():
    _batch_set(products_col, "qr_id", "products", "products")


def sync_scanner_processes():
    _batch_set(scanner_col, "scan_id", "scanner_processes", "scanner_processes")


def sync_assembly_processes():
    _batch_set(assembly_col, "assembly_id", "assembly_processes", "assembly_processes")


def sync_dispatch_processes():
    _batch_set(dispatch_col, "dispatch_id", "dispatch_processes", "dispatch_processes")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 65)
    log.info("MongoDB → Firebase RTDB  full sync")
    log.info("=" * 65)

    grand_ok = grand_err = 0

    for fn in [
        sync_job_cards,
        sync_qr_master,
        sync_products,
        sync_scanner_processes,
        sync_assembly_processes,
        sync_dispatch_processes,
    ]:
        try:
            fn()
        except Exception as exc:
            log.error("Unhandled error in %s: %s", fn.__name__, exc)
            grand_err += 1

    log.info("=" * 65)
    log.info("Sync complete ✓")
    log.info("=" * 65)
