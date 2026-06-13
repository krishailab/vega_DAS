"""
Firebase Realtime Database client for Vega Track.

Initializes Firebase Admin SDK and provides helper functions to sync data
to the Firebase Realtime Database. All writes are fire-and-forget —
failures are logged but never block the API response or raise HTTP errors.
"""

import os
import logging
from datetime import datetime, date
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

logger = logging.getLogger("firebase_client")

# Thread pool executor to run Firebase requests in the background
_executor = ThreadPoolExecutor(max_workers=10)

# Module-level flag to track initialisation state
_firebase_initialized = False
_db = None


def escape_firebase_key(key: str) -> str:
    """Escapes invalid Firebase Realtime Database key characters."""
    if not isinstance(key, str):
        return key
    return (
        key.replace(".", "%2E")
        .replace("$", "%24")
        .replace("#", "%23")
        .replace("[", "%5B")
        .replace("]", "%5D")
        .replace("/", "%2F")
    )


def _serialize_for_firebase(data):
    if isinstance(data, dict):
        return {k: _serialize_for_firebase(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_serialize_for_firebase(item) for item in data]
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    # Catch-all for bson ObjectId or other exotic types
    if hasattr(data, "__str__") and not isinstance(data, (str, int, float, bool)):
        try:
            import json
            json.dumps(data)          # quick serialisability check
            return data
        except (TypeError, ValueError):
            return str(data)
    return data


def init_firebase():
    global _firebase_initialized, _db

    if _firebase_initialized:
        return
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "")
    database_url = os.getenv("FIREBASE_DATABASE_URL", "")

    if not database_url:
        logger.warning("FIREBASE_DATABASE_URL not set — Firebase sync disabled")
        return

    if not service_account_path or not os.path.exists(service_account_path):
        logger.warning(
            "Firebase service-account file not found at '%s' — Firebase sync disabled",
            service_account_path,
        )
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, db as firebase_db

        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred, {"databaseURL": database_url})
        _db = firebase_db
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialised successfully")
    except Exception:
        logger.exception("Failed to initialise Firebase Admin SDK")


def set_to_rtdb(path: str, data: dict):
    """Set (overwrite) data at *path* in the Realtime Database."""
    if not _firebase_initialized or _db is None:
        return
    try:
        safe = _serialize_for_firebase(data)
        def _bg_set():
            try:
                ref = _db.reference(path)
                ref.set(safe)
            except Exception:
                logger.exception("Firebase SET failed for path '%s'", path)
        _executor.submit(_bg_set)
    except Exception:
        logger.exception("Firebase SET dispatch failed for path '%s'", path)


def update_rtdb(path: str, data: dict):
    """Merge *data* into the node at *path*."""
    if not _firebase_initialized or _db is None:
        return
    try:
        safe = _serialize_for_firebase(data)
        def _bg_update():
            try:
                ref = _db.reference(path)
                ref.update(safe)
            except Exception:
                logger.exception("Firebase UPDATE failed for path '%s'", path)
        _executor.submit(_bg_update)
    except Exception:
        logger.exception("Firebase UPDATE dispatch failed for path '%s'", path)


def delete_from_rtdb(path: str):
    """Delete the node at *path*."""
    if not _firebase_initialized or _db is None:
        return
    try:
        def _bg_delete():
            try:
                ref = _db.reference(path)
                ref.delete()
            except Exception:
                logger.exception("Firebase DELETE failed for path '%s'", path)
        _executor.submit(_bg_delete)
    except Exception:
        logger.exception("Firebase DELETE dispatch failed for path '%s'", path)


# ──────────────────────────────────────────────────────────────────
# Domain-specific convenience wrappers
# ──────────────────────────────────────────────────────────────────

def sync_scan(scan_dict: dict):
    """Sync a scanner_process record to Firebase."""
    scan_id = scan_dict.get("scan_id")
    if not scan_id:
        return
    clean = {k: v for k, v in scan_dict.items() if k != "_id"}
    set_to_rtdb(f"/scanner_processes/{scan_id}", clean)


def sync_assembly(assembly_dict: dict):
    """Sync an assembly_process record to Firebase."""
    assembly_id = assembly_dict.get("assembly_id")
    if not assembly_id:
        return
    clean = {k: v for k, v in assembly_dict.items() if k != "_id"}
    set_to_rtdb(f"/assembly_processes/{assembly_id}", clean)


def sync_dispatch(dispatch_dict: dict):
    """Sync a dispatch_process record to Firebase."""
    dispatch_id = dispatch_dict.get("dispatch_id")
    if not dispatch_id:
        return
    clean = {k: v for k, v in dispatch_dict.items() if k != "_id"}
    set_to_rtdb(f"/dispatch_processes/{dispatch_id}", clean)


def sync_qr_master(qr_dict: dict):
    """Sync a qr_master record to Firebase."""
    qr_id = qr_dict.get("qr_id")
    if not qr_id:
        return
    clean = {k: v for k, v in qr_dict.items() if k != "_id"}
    set_to_rtdb(f"/qr_master/{escape_firebase_key(qr_id)}", clean)


def sync_qr_masters_batch(qr_dicts: list[dict]):
    """Sync multiple qr_master records to Firebase in a single batch request."""
    if not _firebase_initialized or _db is None or not qr_dicts:
        return
    try:
        updates = {}
        for qr_dict in qr_dicts:
            qr_id = qr_dict.get("qr_id")
            if qr_id:
                clean = {k: v for k, v in qr_dict.items() if k != "_id"}
                updates[f"qr_master/{escape_firebase_key(qr_id)}"] = _serialize_for_firebase(clean)
        
        if updates:
            def _bg_batch():
                try:
                    ref = _db.reference("/")
                    ref.update(updates)
                except Exception:
                    logger.exception("Firebase batch sync failed")
            _executor.submit(_bg_batch)
    except Exception:
        logger.exception("Firebase batch sync submission failed")


def sync_product(product_dict: dict):
    """Sync a product record to Firebase."""
    qr_id = product_dict.get("qr_id")
    if not qr_id:
        return
    clean = {k: v for k, v in product_dict.items() if k != "_id"}
    set_to_rtdb(f"/products/{escape_firebase_key(qr_id)}", clean)


def sync_job_card(jobcard_dict: dict):
    """Sync a job_card record to Firebase."""
    jobcard_id = jobcard_dict.get("jobcard_id")
    if not jobcard_id:
        return
    clean = {k: v for k, v in jobcard_dict.items() if k != "_id"}
    set_to_rtdb(f"/job_cards/{jobcard_id}", clean)
