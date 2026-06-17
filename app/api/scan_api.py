from typing import List, Union, Any
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Query
import uuid
import os
import shutil
from datetime import datetime, timedelta
from .. import schemas, utils, auth
from ..database import (
    scanner_processes_collection, products_collection,
    assembly_processes_collection, dispatch_processes_collection,
    users_collection, stations_collection, qr_master_collection,
    job_cards_collection, parts_collection, processes_collection,
    product_variants_collection, product_submodels_collection, product_models_collection
)
from ..firebase_client import sync_scan, sync_assembly, sync_dispatch, sync_product, sync_qr_master, update_rtdb

router = APIRouter(prefix="/scan", tags=["Scanning"])

class ScanOperations:
    @staticmethod
    def scan_part(scan: schemas.ScannerProcessDetailCreate, current_user: dict):
        assigned_station_id = current_user.get("assigned_station_id")
        if not assigned_station_id:
            raise HTTPException(status_code=400, detail={"message": "You must assign a station before scanning", "color": "#6c757d"})

        station = stations_collection.find_one({"station_id": assigned_station_id})
        if not station:
            raise HTTPException(status_code=400, detail={"message": "Assigned station not found", "color": "#6c757d"})
        process_name = station.get("process", "Unknown Process")

        master_admin_id = current_user.get("master_admin_id") or current_user["user_id"]

        # ── Read 1: qr_master (single read, reused throughout) ───────────────
        qr_master = qr_master_collection.find_one({"qr_id": scan.qr_id})
        if not qr_master:
            raise HTTPException(status_code=400, detail={"message": "Invalid QR Code", "color": "#6c757d"})

        qr_part_id = qr_master.get("part_id")

        # ── Station part validation (reuse qr_part_id from qr_master) ────────
        station_part_id = station.get("part_id")
        if station_part_id and qr_part_id:
            if qr_part_id != station_part_id:
                # Check BOX exception — only read parts if types differ
                scanned_part = parts_collection.find_one({"part_id": qr_part_id}, {"name": 1})
                is_box = scanned_part and scanned_part.get("name") == "BOX"
                if not is_box:
                    raise HTTPException(status_code=403, detail={"message": "This Part does not belong to your work", "color": "#6c757d"})

        # ── Read 2: latest scan for this QR at this process ──────────────────
        latest_process = scanner_processes_collection.find_one(
            {"qr_id": scan.qr_id, "process_name": process_name},
            sort=[("start_time", -1)]
        )
        if latest_process:
            st = latest_process.get("inspection_status")
            if st == "OKAY":
                raise HTTPException(status_code=400, detail={"message": f"Part has already successfully completed {process_name}", "color": "#ffc107"})
            if st == "REJECTED":
                raise HTTPException(status_code=400, detail={"message": f"Part was REJECTED during {process_name} and cannot be scanned again", "color": "#dc3545"})

        # ── Read 3: product (check SCRAPPED / initialize) ─────────────────────
        product = products_collection.find_one({"qr_id": scan.qr_id})
        if product:
            if product.get("overall_status") == "SCRAPPED":
                raise HTTPException(status_code=400, detail={"message": "Part is locked out: SCRAPPED", "color": "#dc3545"})
        else:
            product_doc = {
                "qr_id": scan.qr_id,
                "master_admin_id": master_admin_id,
                "overall_status": "WIP",
                "created_at": utils.get_current_time()
            }
            products_collection.insert_one(product_doc)
            sync_product(product_doc)
            qr_master_collection.update_one({"qr_id": scan.qr_id}, {"$set": {"status": "IN USE"}})
            update_rtdb(f"/qr_master/{scan.qr_id}", {"status": "IN USE"})
            if qr_master.get("jobcard_id"):
                job_cards_collection.update_one(
                    {"jobcard_id": qr_master["jobcard_id"]},
                    {"$set": {"status": "IN PROGRESS"}}
                )
                update_rtdb(f"/job_cards/{qr_master['jobcard_id']}", {"status": "IN PROGRESS"})

        # ── Read 4: global latest for REWORKED/REJECTED check ────────────────
        # Reuse latest_process for the scan side (already fetched above — it IS the global latest
        # for this process; for a true global we need the unrestricted query)
        global_latest_scan = scanner_processes_collection.find_one(
            {"qr_id": scan.qr_id}, sort=[("start_time", -1)]
        )
        global_latest_asm = assembly_processes_collection.find_one(
            {"qr_ids": scan.qr_id}, sort=[("start_time", -1)]
        )

        global_latest = None
        if global_latest_scan and global_latest_asm:
            global_latest = global_latest_scan if global_latest_scan["start_time"] > global_latest_asm["start_time"] else global_latest_asm
        else:
            global_latest = global_latest_scan or global_latest_asm

        if global_latest and global_latest.get("inspection_status") == "REJECTED":
            raise HTTPException(status_code=400, detail={"message": "Part is currently in REJECTED status and cannot proceed", "color": "#dc3545"})

        is_reworked = global_latest and global_latest.get("inspection_status") == "REWORKED"

        # ── Resolve part_name from cached data (no extra DB call) ────────────
        part_name = "Unknown Part"
        if qr_part_id:
            part_doc = parts_collection.find_one({"part_id": qr_part_id}, {"name": 1})
            if part_doc:
                part_name = part_doc.get("name", "Unknown Part")
        elif qr_master.get("jobcard_id"):
            jc = job_cards_collection.find_one({"jobcard_id": qr_master["jobcard_id"]}, {"part_model": 1})
            if jc:
                part_name = jc.get("part_model", "Unknown Part")

        # ── Build scan record ─────────────────────────────────────────────────
        now = utils.get_current_time()
        scan_dict = scan.model_dump() if hasattr(scan, "model_dump") else scan.dict()
        scan_dict["process_name"] = process_name
        scan_dict["part_name"] = part_name
        scan_dict["station_name"] = station.get("name", "Unknown Station")
        scan_dict["station_comment"] = station.get("comment")
        scan_dict["scan_id"] = utils.generate_custom_id("SCN", scanner_processes_collection, "scan_id")
        scan_dict["station_id"] = assigned_station_id
        scan_dict["scanner_id"] = current_user["user_id"]
        scan_dict["scanner_name"] = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        scan_dict["inspection_status"] = "REWORKED" if is_reworked else "OKAY"
        scan_dict["is_latest"] = True
        scan_dict["start_time"] = now
        scan_dict["end_time"] = None
        scan_dict["inspector_id"] = None
        scan_dict["reject_reason"] = None
        scan_dict["plant_id"] = current_user.get("plant_id")
        scan_dict["plant_name"] = current_user.get("plant_name")
        scan_dict["plant_address"] = current_user.get("plant_address")

        # ── Resolve station-based jobcard (single indexed lookup) ──────────────
        # is_active flag is maintained by _update_station_jobcards_fifo in background.
        # Resolved BEFORE insert so it's persisted to DB — history endpoint reads it directly.
        if assigned_station_id:
            active_st_jc = job_cards_collection.find_one(
                {"station_ids": assigned_station_id, "is_active": True},
                {"jobcard_id": 1}
            )
            if active_st_jc:
                scan_dict["station_jobcard_id"] = active_st_jc["jobcard_id"]

        # ── Critical write: insert new scan record ────────────────────────────
        scanner_processes_collection.insert_one(scan_dict)
        scan_dict.pop("_id", None)
        sync_scan(scan_dict)  # already async via ThreadPoolExecutor

        # ── Background: bookkeeping writes that don't affect the response ─────
        _scanner_id = current_user["user_id"]
        _qr_id = scan.qr_id
        _end_time = now

        import threading
        def _bg_bookkeeping():
            # Close the scanner's previous open scan (end_time driven by next scan)
            scanner_processes_collection.update_many(
                {"scanner_id": _scanner_id, "end_time": None},
                {"$set": {"end_time": _end_time}}
            )
            # Mark previous records as not latest
            scanner_processes_collection.update_many({"qr_id": _qr_id, "is_latest": True}, {"$set": {"is_latest": False}})
            assembly_processes_collection.update_many({"qr_ids": _qr_id, "is_latest": True}, {"$set": {"is_latest": False}})

        threading.Thread(target=_bg_bookkeeping, daemon=True).start()

        # ── Background: job card completion checks ────────────────────────────
        # Step-1 jobcard (owns the QR directly) — individual check
        if qr_master.get("jobcard_id"):
            _check_and_update_job_card_completion(qr_master["jobcard_id"])

        # Step-2+ station-based jobcards — FIFO update for ALL jobcards at this
        # station in one shot (avoids each seeing the full scan count independently)
        if assigned_station_id:
            _trigger_station_fifo(assigned_station_id)

        return scan_dict


    @staticmethod
    def inspect_part(qr_id: str, inspection_status: str, reject_reason: str, image: UploadFile, current_user: dict):
        if not current_user.get("assigned_station_id"):
            raise HTTPException(status_code=400, detail="You must assign a station before inspecting")
            

        active_process = scanner_processes_collection.find_one(
            {"qr_id": qr_id, "inspection_status": {"$in": ["PENDING", "OKAY", "REWORKED"]}},
            sort=[("start_time", -1)]
        )
        is_assembly = False
        
        if not active_process:
            active_process = assembly_processes_collection.find_one(
                {"qr_ids": qr_id, "inspection_status": {"$in": ["PENDING", "OKAY", "REWORKED"]}},
                sort=[("start_time", -1)]
            )
            if active_process:
                is_assembly = True
                
        if not active_process:
            raise HTTPException(status_code=404, detail="No pending process found for this QR code to inspect")
            
        if inspection_status not in ["OKAY", "REWORKED", "REJECTED"]:
            raise HTTPException(status_code=400, detail="Invalid inspection status")
            
        if inspection_status == "REJECTED" and not image:
            raise HTTPException(status_code=400, detail="An image must be uploaded when rejecting a part")
            
        update_data = {
            "inspection_status": inspection_status,
            "end_time": utils.get_current_time(),
            "inspector_id": current_user["user_id"],
            "inspector_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        }
        
        if reject_reason:
            update_data["reject_reason"] = reject_reason
            
        if image:
            master_admin_id = current_user.get("master_admin_id") or current_user["user_id"]
            dir_path = os.path.join("qrcodes", master_admin_id, "Rejections")
            os.makedirs(dir_path, exist_ok=True)
            
            ext = os.path.splitext(image.filename)[1]
            if not ext:
                ext = ".jpeg"
                
            process_id_key = "assembly_id" if is_assembly else "scan_id"
            file_name = f"{active_process[process_id_key]}{ext}"
            file_path = os.path.join(dir_path, file_name)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
                
            update_data["rejection_image"] = file_path
            
        if is_assembly:
            assembly_processes_collection.update_one(
                {"assembly_id": active_process["assembly_id"]},
                {"$set": update_data}
            )
            updated = assembly_processes_collection.find_one({"assembly_id": active_process["assembly_id"]})
        else:
            scanner_processes_collection.update_one(
                {"scan_id": active_process["scan_id"]},
                {"$set": update_data}
            )
            updated = scanner_processes_collection.find_one({"scan_id": active_process["scan_id"]})
        
        if inspection_status == "REJECTED":
            products_collection.update_one(
                {"qr_id": qr_id},
                {"$set": {"overall_status": "SCRAPPED"}}
            )
            update_rtdb(f"/products/{qr_id}", {"overall_status": "SCRAPPED"})
            # Check for job card completion
            qr_rec = qr_master_collection.find_one({"qr_id": qr_id})
            if qr_rec and qr_rec.get("jobcard_id"):
                _check_and_update_job_card_completion(qr_rec["jobcard_id"])
            
        updated.pop("_id", None)
        # Sync updated inspection to Firebase
        if is_assembly:
            sync_assembly(updated)
        else:
            sync_scan(updated)
        return updated

    @staticmethod
    def get_user_history(user_id: str, current_user: dict):
        if current_user["role"] not in ["Super Admin", "Master Admin", "B2B Admin"]:
            if current_user["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only view your own history.")
        
        if current_user["role"] == "Master Admin":
            target = users_collection.find_one({"user_id": user_id})
            if not target:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Master Admin can view their own history or any sub-user history
            if target["role"] not in ["Reader", "Inspector", "Linker"] and target["user_id"] != current_user["user_id"]:
                 raise HTTPException(status_code=403, detail="Access denied. Master Admins can only view sub-user history.")

        cache = {}
        def get_name(uid):
            if not uid: return None
            if uid in cache: return cache[uid]
            u = users_collection.find_one({"user_id": uid})
            name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() if u else "Unknown"
            cache[uid] = name
            return name
            
        part_cache = {}
        def get_part_name(qid):
            if not qid: return "Unknown Part"
            if qid in part_cache: return part_cache[qid]
            q_rec = qr_master_collection.find_one({"qr_id": qid})
            name = "Unknown Part"
            if q_rec:
                pid = q_rec.get("part_id")
                if pid:
                    part = parts_collection.find_one({"part_id": pid})
                    if part: name = part.get("name", "Unknown Part")
                else:
                    # Fallback for old records
                    job = job_cards_collection.find_one({"jobcard_id": q_rec["jobcard_id"]})
                    if job: name = job["part_model"]
            part_cache[qid] = name
            return name

        history = []
        
        scans = list(scanner_processes_collection.find({"scanner_id": user_id}))
        for s in scans:
            s.pop("_id", None)
            s["activity_type"] = "Scan"
            if not s.get("scanner_name"):
                s["scanner_name"] = get_name(s.get("scanner_id"))
            if s.get("inspector_id") and not s.get("inspector_name"):
                s["inspector_name"] = get_name(s.get("inspector_id"))
            history.append(s)
            
        inspections = list(scanner_processes_collection.find({"inspector_id": user_id}))
        for i in inspections:
            i.pop("_id", None)
            i["activity_type"] = "Inspection (Part)"
            if not i.get("scanner_name"):
                i["scanner_name"] = get_name(i.get("scanner_id"))
            if not i.get("inspector_name"):
                i["inspector_name"] = get_name(i.get("inspector_id"))
            history.append(i)
            
        links = list(assembly_processes_collection.find({"linker_id": user_id}))
        for l in links:
            l.pop("_id", None)
            l["activity_type"] = "Assembly/Link"
            if not l.get("linker_name"):
                l["linker_name"] = get_name(l.get("linker_id"))
            if l.get("inspector_id") and not l.get("inspector_name"):
                l["inspector_name"] = get_name(l.get("inspector_id"))
            l["qr_ids"] = _format_nested_qr_ids(l.get("qr_ids", []))
            history.append(l)
            
        asm_inspections = list(assembly_processes_collection.find({"inspector_id": user_id}))
        for ai in asm_inspections:
            ai.pop("_id", None)
            ai["activity_type"] = "Inspection (Assembly)"
            if not ai.get("linker_name"):
                ai["linker_name"] = get_name(ai.get("linker_id"))
            if not ai.get("inspector_name"):
                ai["inspector_name"] = get_name(ai.get("inspector_id"))
            ai["qr_ids"] = _format_nested_qr_ids(ai.get("qr_ids", []))
            history.append(ai)
            
        dispatches = list(dispatch_processes_collection.find({"linker_id": user_id}))
        for d in dispatches:
            d.pop("_id", None)
            d["activity_type"] = "Dispatch"
            if not d.get("linker_name"):
                d["linker_name"] = get_name(d.get("linker_id"))
            d["qr_ids"] = [{"qr_id": q, "part_name": get_part_name(q)} for q in d.get("qr_ids", [])]
            history.append(d)
        _station_jc_cache: dict = {}

        def _get_station_jobcards(sid: str):
            if sid in _station_jc_cache:
                return _station_jc_cache[sid]
            jcs = list(
                job_cards_collection.find(
                    {"station_ids": sid},
                    {"jobcard_id": 1, "jobcard_no": 1, "quantity": 1,
                     "status": 1, "completion_percentage": 1, "created_at": 1}
                ).sort("created_at", 1)
            )
            for jc in jcs:
                jc.pop("_id", None)
            _station_jc_cache[sid] = jcs
            return jcs

        # Cache: station_id → count of OKAY unique QRs up to each scan's time
        # We resolve per-scan using a position in the FIFO queue.
        for entry in history:
            if entry.get("activity_type") not in ("Scan", "Inspection (Part)"):
                continue
            sid = entry.get("station_id")
            process_name_entry = entry.get("process_name")
            scan_time = entry.get("start_time")
            if not sid or not process_name_entry or not scan_time:
                continue

            jcs = _get_station_jobcards(sid)
            if not jcs:
                continue

            # Count how many unique OKAY QRs at this station existed UP TO this scan time
            okay_qr_ids_upto: set = set()
            for doc in scanner_processes_collection.find(
                {
                    "station_id": sid,
                    "process_name": process_name_entry,
                    "inspection_status": "OKAY",
                    "start_time": {"$lte": scan_time}
                },
                {"qr_id": 1, "_id": 0}
            ):
                if doc.get("qr_id"):
                    okay_qr_ids_upto.add(doc["qr_id"])

            total_upto = len(okay_qr_ids_upto)

            # Walk FIFO queue to find which jobcard slot this scan's position falls into
            cumulative = 0
            matched_jc = None
            for jc in jcs:
                qty = jc.get("quantity") or 0
                if qty <= 0:
                    continue
                if total_upto > cumulative:
                    matched_jc = jc
                    if total_upto <= cumulative + qty:
                        break
                cumulative += qty

            if matched_jc:
                entry["station_jobcard_id"] = matched_jc.get("jobcard_id")


        history.sort(key=lambda x: x["start_time"] if x.get("start_time") else datetime.min, reverse=True)
        return history
            
    @staticmethod
    def check_qr(qr_id: str):
        qr_rec = qr_master_collection.find_one({"qr_id": qr_id})
        part_name = get_part_name(qr_id)
        
        if not qr_rec:
            return {"status": "external qr", "part_name": part_name, "error_color_code": "#6c757d"}
            
        # Find latest scan process
        latest_scan = scanner_processes_collection.find_one(
            {"qr_id": qr_id},
            sort=[("start_time", -1)]
        )
        
        # Find latest assembly process
        latest_asm = assembly_processes_collection.find_one(
            {"component_ids": qr_id},
            sort=[("start_time", -1)]
        )

        # Find latest dispatch process
        latest_dsp = dispatch_processes_collection.find_one(
            {"qr_ids": qr_id},
            sort=[("start_time", -1)]
        )
        
        latest_process = None
        processes = [p for p in [latest_scan, latest_asm, latest_dsp] if p]
        if processes:
            latest_process = max(processes, key=lambda x: x["start_time"])
            
        if latest_process:
            inspection_status = latest_process.get("inspection_status")
            if inspection_status in ["OKAY", "REWORKED", "REJECTED"]:
                color_map = {
                    "OKAY": "#ffc107",      # Yellow - alredy scan
                    "REJECTED": "#dc3545",  # Red - rejected
                    "REWORKED": "#fd7e14"   # Orange - proces vaildation
                }
                color = color_map.get(inspection_status, "#6c757d")
                return {"status": inspection_status, "part_name": part_name, "error_color_code": color}
            
        return {"status": "NOT IN USE", "part_name": part_name, "error_color_code": "#28a745"}

@router.post("/", response_model=schemas.ScannerProcessDetail)
def scan_part(
    scan: schemas.ScannerProcessDetailCreate, 
    current_user: dict = Depends(auth.RoleChecker(["Reader", "Inspector", "Super Admin", "Master Admin"]))
):
    return ScanOperations.scan_part(scan, current_user)

@router.put("/inspect")
def inspect_part(
    qr_id: str = Form(...),
    inspection_status: str = Form(...),
    reject_reason: str = Form(None),
    image: UploadFile = File(None),
    current_user: dict = Depends(auth.RoleChecker(["Inspector", "Super Admin", "Master Admin"]))
):
    return ScanOperations.inspect_part(qr_id, inspection_status, reject_reason, image, current_user)

def _flatten_qr_ids(nested_ids):
    """Recursively extract all individual QR ID strings from a nested structure.
    E.g. [["q","w"], "e"] -> ["q", "w", "e"]
    """
    flat = []
    for item in nested_ids:
        if isinstance(item, list):
            flat.extend(_flatten_qr_ids(item))
        else:
            flat.append(item)
    return flat


def _format_nested_qr_ids(qr_ids):
    result = []
    for item in qr_ids:
        if isinstance(item, list):
            result.append(_format_nested_qr_ids(item))
        else:
            result.append({"qr_id": item, "part_name": get_part_name(item)})
    return result


def _build_nested_structure(qr_ids, assemblies_to_consume):
    """Build the nested qr_ids structure.
    For each QR that belongs to a consumed assembly, replace it with the
    assembly's qr_ids (preserving its own nesting). QRs not in any consumed
    assembly stay as plain strings.
    
    assemblies_to_consume: dict mapping assembly_id -> assembly doc
    Returns the nested list, e.g. [["q","w"], "e"]
    """
    # Map each QR to the assembly it came from (if any)
    qr_to_asm_id = {}
    for asm_id, asm_doc in assemblies_to_consume.items():
        for qid in _flatten_qr_ids(asm_doc.get("qr_ids", [])):
            qr_to_asm_id[qid] = asm_id

    nested = []
    consumed_asm_ids = set()
    for qr in qr_ids:
        asm_id = qr_to_asm_id.get(qr)
        if asm_id and asm_id not in consumed_asm_ids:
            # Insert the whole previous assembly's qr_ids as a nested group
            nested.append(assemblies_to_consume[asm_id]["qr_ids"])
            consumed_asm_ids.add(asm_id)
        elif asm_id and asm_id in consumed_asm_ids:
            # Already added as part of the nested group, skip
            continue
        else:
            nested.append(qr)
    return nested


@router.post("/link", response_model=schemas.AssemblyProcessDetail)
def link_parts(
    link: schemas.AssemblyLinkCreate,
    current_user: dict = Depends(auth.RoleChecker(["Linker"]))
):
    assigned_station_id = current_user.get("assigned_station_id")
    if not assigned_station_id:
        raise HTTPException(status_code=400, detail="You must assign a station before linking")
        
    station = stations_collection.find_one({"station_id": assigned_station_id})
    if not station:
        raise HTTPException(status_code=400, detail="Assigned station not found")
    if station.get("is_dispatch"):
        raise HTTPException(status_code=400, detail="This station is for dispatch. Please use the /dispatch endpoint.")
    process_name = station.get("name", "Assembly Process")
        

    capacity = current_user.get("linker_capacity") or station.get("linker_capacity")
    if not capacity:
        raise HTTPException(status_code=400, detail="Linker capacity not set for this station or user")
        
    # The number of "members" should match capacity.
    if len(link.qr_ids) != capacity:
        raise HTTPException(status_code=400, detail=f"You must provide exactly {capacity} items based on your capacity")
        
    # The incoming qr_ids are always flat strings from the scanner
    incoming_qr_ids = link.qr_ids

    if len(set(incoming_qr_ids)) != len(incoming_qr_ids):
        raise HTTPException(status_code=400, detail="Duplicate QR IDs detected in the linkage request")
        
    master_admin_id = current_user.get("master_admin_id") or current_user["user_id"]
    
    
    # --- Phase 1: Detect active assemblies that will be consumed (nested linking) ---
    assemblies_to_consume = {}  # assembly_id -> assembly doc
    extra_qr_ids = set()  # QRs pulled in from consumed assemblies
    
    for qr in incoming_qr_ids:
        # Search in component_ids to find if this QR is part of any active assembly
        active_asm = assembly_processes_collection.find_one({"component_ids": qr, "is_latest": True})
        if active_asm and active_asm["assembly_id"] not in assemblies_to_consume:
            assemblies_to_consume[active_asm["assembly_id"]] = active_asm
            # Pull all QRs from that assembly into our working set
            for aqr in _flatten_qr_ids(active_asm.get("qr_ids", [])):
                if aqr not in incoming_qr_ids:
                    extra_qr_ids.add(aqr)
    
    # All flat QR IDs involved in this new assembly (incoming + pulled from consumed assemblies)
    all_flat_qr_ids = list(incoming_qr_ids) + list(extra_qr_ids)
    
    if len(set(all_flat_qr_ids)) != len(all_flat_qr_ids):
        raise HTTPException(status_code=400, detail="Duplicate QR IDs detected across assemblies being merged")
    
    # Station setting always overrides user setting (even when 0 — use is-not-None to avoid falsy-zero bug)
    _station_gqn = station.get("global_qr_number")
    _user_gqn = current_user.get("global_qr_number")
    external_qr_limit = _station_gqn if _station_gqn is not None else (_user_gqn if _user_gqn is not None else 0)
    internal_qr_count = capacity - external_qr_limit
    if internal_qr_count < 0:
        internal_qr_count = 0
    
    part_id_to_qr = {}

    external_qrs_in_this_session = set()  # only truly unregistered QRs auto-registered this session
    box_qr_count = 0  # counts only new/unregistered QRs auto-registered as BOX

    for i, qr in enumerate(incoming_qr_ids):
        is_internal = (i < internal_qr_count)

        qr_rec = qr_master_collection.find_one({"qr_id": qr})

        if qr_rec:
            pid = qr_rec.get("part_id")
            if not pid:
                job = job_cards_collection.find_one({"jobcard_id": qr_rec.get("jobcard_id")})
                pid = job.get("part_id") if job else None

            if not pid:
                raise HTTPException(status_code=400, detail=f"Could not determine part type for QR {qr}")

            part = parts_collection.find_one({"part_id": pid})
            part_name = part.get("name", pid) if part else pid
            is_box_qr = (part_name == "BOX")
            already_linked = assembly_processes_collection.find_one({
                "component_ids": qr,
                "process_name": process_name,
                "inspection_status": "OKAY",
                "is_latest": True
            })
            if already_linked:
                raise HTTPException(
                    status_code=400,
                    detail=f"{part_name} ({qr}) is already linked for process '{process_name}'. Each QR can only be linked once per process."
                )
            if pid in part_id_to_qr:
                raise HTTPException(
                    status_code=400,
                    detail=f"Conflict: Multiple parts of type '{part_name}' detected. Each component in the assembly must be a distinct part model."
                )

            part_id_to_qr[pid] = qr
            product = products_collection.find_one({"qr_id": qr})
            if product:
                if product.get("overall_status") == "SCRAPPED":
                    raise HTTPException(status_code=400, detail=f"Part {qr} is locked out: SCRAPPED")
            else:
                _prod_doc = {
                    "qr_id": qr,
                    "master_admin_id": qr_rec["master_admin_id"],
                    "overall_status": "WIP",
                    "created_at": utils.get_current_time()
                }
                products_collection.insert_one(_prod_doc)
                sync_product(_prod_doc)
                qr_master_collection.update_one(
                    {"qr_id": qr},
                    {"$set": {"status": "IN USE"}}
                )
                update_rtdb(f"/qr_master/{qr}", {"status": "IN USE"})
        else:
            external_part_id = get_or_create_external_part()
            if external_part_id in part_id_to_qr:
                raise HTTPException(
                    status_code=400,
                    detail="Conflict: Multiple parts of type 'BOX' detected. Each component in the assembly must be a distinct part model."
                )
            
            part_id_to_qr[external_part_id] = qr
            _qr_doc = {
                "qr_id": qr,
                "jobcard_id": None,
                "part_id": external_part_id,
                "master_admin_id": master_admin_id,
                "status": "IN USE",
                "created_at": utils.get_current_time()
            }
            qr_master_collection.insert_one(_qr_doc)
            sync_qr_master(_qr_doc)
            _prod_doc = {
                "qr_id": qr,
                "master_admin_id": master_admin_id,
                "overall_status": "OKAY",
                "created_at": utils.get_current_time()
            }
            products_collection.insert_one(_prod_doc)
            sync_product(_prod_doc)
            # Truly external — counts against global_qr_number
            external_qrs_in_this_session.add(qr)
            box_qr_count += 1

    # --- Enforce global_qr_number: limit BOX/external QRs per assembly ---
    if external_qr_limit is not None and box_qr_count > external_qr_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Too many BOX/external QRs: {box_qr_count} scanned but the limit is {external_qr_limit} (global_qr_number)."
        )

    # For nested linking, we also validate all extra QRs as they must be internal.
    # If an extra QR has the same part type as an INCOMING QR, the incoming QR takes
    # precedence and the old extra QR is dropped (it is being replaced in the new assembly).
    replaced_extra_qrs = set()

    for qr in list(extra_qr_ids):
        qr_rec = qr_master_collection.find_one({"qr_id": qr})
        if not qr_rec:
            continue # Should not happen as they come from existing assemblies

        # --- Validate nested QR: must not already be linked (OKAY) for this same process ---
        already_linked_nested = assembly_processes_collection.find_one({
            "component_ids": qr,
            "process_name": process_name,
            "inspection_status": "OKAY",
            "is_latest": True
        })
        if already_linked_nested:
            pname_nested = "Unknown Part"
            if qr_rec.get("part_id"):
                p_nested = parts_collection.find_one({"part_id": qr_rec["part_id"]})
                if p_nested:
                    pname_nested = p_nested.get("name", "Unknown Part")
            raise HTTPException(
                status_code=400,
                detail=f"{pname_nested} ({qr}) from nested assembly is already linked for process '{process_name}'. Each QR can only be linked once per process."
            )

        pid = qr_rec.get("part_id") or (job_cards_collection.find_one({"jobcard_id": qr_rec.get("jobcard_id")}).get("part_id") if qr_rec.get("jobcard_id") else None)
        if pid and pid in part_id_to_qr and part_id_to_qr[pid] != qr:
            p_name = get_part_name(qr)
            raise HTTPException(
                status_code=400,
                detail=f"Conflict: Multiple parts of type '{p_name}' detected. This assembly (or one of its sub-assemblies) already contains a component of this type."
            )

        if pid:
            part_id_to_qr[pid] = qr

        product = products_collection.find_one({"qr_id": qr})
        if product and product.get("overall_status") == "SCRAPPED":
            raise HTTPException(status_code=400, detail=f"Part {qr} from nested assembly is locked out: SCRAPPED")

    # Rebuild all_flat_qr_ids excluding extra QRs that were replaced by incoming QRs
    if replaced_extra_qrs:
        all_flat_qr_ids = [q for q in all_flat_qr_ids if q not in replaced_extra_qrs]

    # Check for exact duplicate assembly (same set of QRs for same process)
    existing_identical = assembly_processes_collection.find_one({
        "process_name": process_name,
        "qr_ids": {"$size": len(all_flat_qr_ids), "$all": all_flat_qr_ids}
    })
    if existing_identical:
        raise HTTPException(status_code=400, detail="This exact assembly has already been successfully linked for this process.")

    for qr in all_flat_qr_ids:
        if qr in external_qrs_in_this_session:
            continue
            
        qr_rec = qr_master_collection.find_one({"qr_id": qr})
        if not qr_rec or qr in external_qrs_in_this_session:
            continue

        if qr_rec.get("part_id"):
            _part = parts_collection.find_one({"part_id": qr_rec["part_id"]})
            if _part and _part.get("name") == "BOX":
                continue

        # Skip "already consumed" check for QRs that are part of assemblies we're about to consume
        active_asm = assembly_processes_collection.find_one({"component_ids": qr, "is_latest": True})
        if active_asm:
            if active_asm["assembly_id"] in assemblies_to_consume:
                # This QR is in an assembly we're consuming - that's expected
                continue
            else:
                raise HTTPException(status_code=400, detail=f"Part {qr} is already consumed in an active assembly ({active_asm['assembly_id']})")

        # Check latest status - MUST be OKAY
        lp_scan = scanner_processes_collection.find_one({"qr_id": qr}, sort=[("start_time", -1)])
        lp_asm = assembly_processes_collection.find_one({"component_ids": qr}, sort=[("start_time", -1)])
        
        latest_rec = None
        if lp_scan and lp_asm:
            latest_rec = lp_scan if lp_scan["start_time"] > lp_asm["start_time"] else lp_asm
        else:
            latest_rec = lp_scan or lp_asm
            
        if not latest_rec or latest_rec.get("inspection_status") != "OKAY":
            qr_rec = qr_master_collection.find_one({"qr_id": qr})
            part_name = "Unknown Part"
            if qr_rec and qr_rec.get("part_id"):
                part = parts_collection.find_one({"part_id": qr_rec["part_id"]})
                if part:
                    part_name = part.get("name", "Unknown Part")
            
            curr_status = latest_rec.get("inspection_status", "NOT SCANNED") if latest_rec else "NOT SCANNED"
            raise HTTPException(status_code=400, detail=f"{part_name} not production ready (Current Status: {curr_status})")
    
    # --- Phase 2: Mark old records as not latest ---
    for qr in all_flat_qr_ids:
        scanner_processes_collection.update_many({"qr_id": qr}, {"$set": {"is_latest": False}})
        assembly_processes_collection.update_many({"qr_ids": qr}, {"$set": {"is_latest": False}})

    # --- Phase 3: Build the nested qr_ids structure ---
    # If there are consumed assemblies, build nested structure: e.g. [[q,w], e]
    # Otherwise, keep it flat: [q, w]
    if assemblies_to_consume:
        nested_qr_ids = _build_nested_structure(incoming_qr_ids, assemblies_to_consume)
    else:
        nested_qr_ids = list(incoming_qr_ids)

    # Look up the process record for full process details
    process_rec = processes_collection.find_one({"name": process_name})
    process_id = process_rec.get("process_id") if process_rec else None

    assembly_doc = {
        "assembly_id": utils.generate_custom_id("ASM", assembly_processes_collection, "assembly_id"),
        "qr_ids": nested_qr_ids,
        "component_ids": all_flat_qr_ids,
        "process_name": process_name,
        "process_id": process_id,
        "station_id": current_user["assigned_station_id"],
        "station_name": station.get("name", "Unknown Station"),
        "station_comment": station.get("comment"),
        "master_admin_id": master_admin_id,
        "linker_id": current_user["user_id"],
        "linker_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "inspection_status": "OKAY",
        "is_latest": True,
        "start_time": utils.get_current_time(),
        "end_time": None,
        "inspector_id": None,
        "reject_reason": None,
        "plant_id": current_user.get("plant_id"),
        "plant_name": current_user.get("plant_name"),
        "plant_address": current_user.get("plant_address")
    }
    
    assembly_processes_collection.insert_one(assembly_doc)
    # Sync assembly to Firebase (use raw doc before response formatting)
    _fb_asm = {k: v for k, v in assembly_doc.items() if k != "_id"}
    sync_assembly(_fb_asm)
    
    # --- Phase 4: Automatic Product and Job Card Status Updates ---
    # If the station's assigned part is "BOX", mark components as CYCLE COMPLETE
    station_part_id = station.get("part_id")
    if station_part_id:
        station_part = parts_collection.find_one({"part_id": station_part_id})
        if station_part and station_part.get("name") == "BOX":
            products_collection.update_many(
                {"qr_id": {"$in": all_flat_qr_ids}},
                {"$set": {"overall_status": "CYCLE COMPLETE"}}
            )
            for _qid in all_flat_qr_ids:
                update_rtdb(f"/products/{_qid}", {"overall_status": "CYCLE COMPLETE"})
    
    # Always check associated job cards for completion after any linkage
    jobcard_ids = qr_master_collection.distinct("jobcard_id", {"qr_id": {"$in": all_flat_qr_ids}})
    for jcid in jobcard_ids:
        if jcid:
            _check_and_update_job_card_completion(jcid)

    # Build response with part names
    def _build_response_qr_ids(ids):
        result = []
        for item in ids:
            if isinstance(item, list):
                result.append(_build_response_qr_ids(item))
            else:
                result.append({"qr_id": item, "part_name": get_part_name(item)})
        return result

    assembly_doc.pop("_id", None)
    assembly_doc["qr_ids"] = _build_response_qr_ids(nested_qr_ids)
    return assembly_doc

@router.post("/dispatch", response_model=schemas.DispatchProcessDetail)
def dispatch_parts(
    link: schemas.AssemblyLinkCreate,
    current_user: dict = Depends(auth.RoleChecker(["Linker"]))
):
    assigned_station_id = current_user.get("assigned_station_id")
    if not assigned_station_id:
        raise HTTPException(status_code=400, detail="You must assign a station before linking")
        
    station = stations_collection.find_one({"station_id": assigned_station_id})
    if not station:
        raise HTTPException(status_code=400, detail="Assigned station not found")
    if not station.get("is_dispatch"):
        raise HTTPException(status_code=400, detail="This station is not configured for dispatch")

    process_name = station.get("name", "Dispatch Process")
    capacity = current_user.get("linker_capacity") or station.get("linker_capacity")
    if not capacity:
        raise HTTPException(status_code=400, detail="Linker capacity not set for this station or user")
        
    if len(link.qr_ids) != capacity:
        raise HTTPException(status_code=400, detail=f"You must provide exactly {capacity} items based on your capacity")
        
    incoming_qr_ids = link.qr_ids
    if len(set(incoming_qr_ids)) != len(incoming_qr_ids):
        raise HTTPException(status_code=400, detail="Duplicate QR IDs detected in the dispatch request")
        
    master_admin_id = current_user.get("master_admin_id") or current_user["user_id"]
    
    # Validation loop
    for qr in incoming_qr_ids:
        # Check for already dispatched in this specific process (prevent double scans)
        already_dispatched = dispatch_processes_collection.find_one({
            "qr_ids": qr,
            "process_name": process_name,
            "is_latest": True
        })
        if already_dispatched:
             raise HTTPException(status_code=400, detail=f"Item {qr} has already been dispatched for process '{process_name}'")

        qr_rec = qr_master_collection.find_one({"qr_id": qr})
        
        if not qr_rec:
            # QR not in DB — auto-register as BOX (external packaging)
            external_part_id = get_or_create_external_part()
            _qr_doc = {
                "qr_id": qr,
                "jobcard_id": None,
                "part_id": external_part_id,
                "master_admin_id": master_admin_id,
                "status": "IN USE",
                "created_at": utils.get_current_time()
            }
            qr_master_collection.insert_one(_qr_doc)
            sync_qr_master(_qr_doc)
            _prod_doc = {
                "qr_id": qr,
                "master_admin_id": master_admin_id,
                "overall_status": "OKAY",
                "created_at": utils.get_current_time()
            }
            products_collection.insert_one(_prod_doc)
            sync_product(_prod_doc)
            continue # External BOX parts are allowed to bypass production-ready checks
            
        # If it exists, check if it's a BOX part (exempt from status checks)
        if qr_rec.get("part_id"):
            part = parts_collection.find_one({"part_id": qr_rec["part_id"]})
            if part and part.get("name") == "BOX":
                continue # BOX parts are packaging, they don't go through scanning
                
        # Check latest status - MUST be OKAY in scan or assembly for internal parts
        lp_scan = scanner_processes_collection.find_one({"qr_id": qr}, sort=[("start_time", -1)])
        lp_asm = assembly_processes_collection.find_one({"component_ids": qr}, sort=[("start_time", -1)])
        
        latest_rec = None
        if lp_scan and lp_asm:
            latest_rec = lp_scan if lp_scan["start_time"] > lp_asm["start_time"] else lp_asm
        else:
            latest_rec = lp_scan or lp_asm
            
        if not latest_rec or latest_rec.get("inspection_status") != "OKAY":
            curr_status = latest_rec.get("inspection_status", "NOT SCANNED") if latest_rec else "NOT SCANNED"
            raise HTTPException(status_code=400, detail=f"Item {qr} not production ready (Current Status: {curr_status})")

    # Mark old records as not latest (exit the line)
    for qr in incoming_qr_ids:
        scanner_processes_collection.update_many({"qr_id": qr}, {"$set": {"is_latest": False}})
        assembly_processes_collection.update_many({"qr_ids": qr}, {"$set": {"is_latest": False}})
        dispatch_processes_collection.update_many({"qr_ids": qr}, {"$set": {"is_latest": False}})

    # Look up the process record
    process_rec = processes_collection.find_one({"name": process_name})
    process_id = process_rec.get("process_id") if process_rec else None

    dispatch_doc = {
        "dispatch_id": utils.generate_custom_id("DSP", dispatch_processes_collection, "dispatch_id"),
        "qr_ids": incoming_qr_ids,
        "process_name": process_name,
        "process_id": process_id,
        "station_id": assigned_station_id,
        "station_name": station.get("name", "Unknown Station"),
        "station_comment": station.get("comment"),
        "master_admin_id": master_admin_id,
        "linker_id": current_user["user_id"],
        "linker_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "inspection_status": "OKAY",
        "is_latest": True,
        "start_time": utils.get_current_time(),
        "end_time": None,
        "inspector_id": None,
        "reject_reason": None,
        "plant_id": current_user.get("plant_id"),
        "plant_name": current_user.get("plant_name"),
        "plant_address": current_user.get("plant_address")
    }
    
    dispatch_processes_collection.insert_one(dispatch_doc)
    _fb_dsp = {k: v for k, v in dispatch_doc.items() if k != "_id"}
    sync_dispatch(_fb_dsp)
    
    # Mark products as DISPATCHED
    products_collection.update_many(
        {"qr_id": {"$in": incoming_qr_ids}},
        {"$set": {"overall_status": "DISPATCHED"}}
    )
    for _qid in incoming_qr_ids:
        update_rtdb(f"/products/{_qid}", {"overall_status": "DISPATCHED"})
    
    # Check associated job cards for completion
    jobcard_ids = qr_master_collection.distinct("jobcard_id", {"qr_id": {"$in": incoming_qr_ids}})
    for jcid in jobcard_ids:
        if jcid:
            _check_and_update_job_card_completion(jcid)
    
    # Build response with part names (FLAT)
    def _build_response_qr_ids_flat(ids):
        return [{"qr_id": q, "part_name": get_part_name(q)} for q in ids]

    dispatch_doc.pop("_id", None)
    dispatch_doc["qr_ids"] = _build_response_qr_ids_flat(incoming_qr_ids)
    return dispatch_doc

def get_or_create_external_part():
    """Look up or create the single shared BOX part used for external/unregistered QR codes.
    Always looks up by name 'BOX' first — guarantees only one BOX part ever exists."""
    box = parts_collection.find_one({"name": "BOX"})
    if box:
        if "type" not in box:
             parts_collection.update_one({"name": "BOX"}, {"$set": {"type": "BOX"}})
        return box["part_id"]

    new_id = utils.generate_custom_id("PTR", parts_collection, "part_id")
    parts_collection.insert_one({
        "part_id": new_id,
        "name": "BOX",
        "type": "BOX",
        "category": "DISPATCH",
        "active": True,
        "created_at": utils.get_current_time()
    })
    return new_id

def ensure_box_part_exists():
    return get_or_create_external_part()

def get_name(uid):
    if not uid: return None
    u = users_collection.find_one({"user_id": uid})
    return f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() if u else "Unknown"

def get_part_id(qid):
    if not qid: return None
    q_rec = qr_master_collection.find_one({"qr_id": qid})
    return q_rec.get("part_id") if q_rec else None

def get_part_name(qid):
    if not qid: return "Unknown Part"
    q_rec = qr_master_collection.find_one({"qr_id": qid})
    if q_rec:
        pid = q_rec.get("part_id")
        if pid:
            part = parts_collection.find_one({"part_id": pid})
            if part: return part.get("name", "Unknown Part")
        
        job_id = q_rec.get("jobcard_id")
        if job_id:
            job = job_cards_collection.find_one({"jobcard_id": job_id})
            return job["part_model"] if job else "Unknown Part"
        return "Unknown Part"
    return "Box"

def get_qr_detail_nested(qid, current_asm=None):
    base_detail = {"qr_id": qid, "part_name": get_part_name(qid)}
    
    query = {"qr_ids": qid}
    if current_asm:
        query["assembly_id"] = {"$ne": current_asm.get("assembly_id")}
        if current_asm.get("start_time"):
            query["start_time"] = {"$lt": current_asm["start_time"]}
            
    prev_asm = assembly_processes_collection.find_one(query, sort=[("start_time", -1)])
    
    if prev_asm:
        nested_list = []
        for mqid in prev_asm["qr_ids"]:
            nested_list.append({"qr_id": mqid, "part_name": get_part_name(mqid)})
        return nested_list
        
    return base_detail

def _get_qr_component_data(qr_id: str, include_dispatch: bool = True):
    
    # ── Fetch qr_master + product in parallel (both needed below) ────────────
    product = products_collection.find_one({"qr_id": qr_id})
    qr_master = qr_master_collection.find_one({"qr_id": qr_id})

    if not product and not qr_master:
        exists_in_asm = assembly_processes_collection.find_one({"component_ids": qr_id})
        if not exists_in_asm:
            return None, None, [], []

    created_at = None
    if product:
        created_at = product.get("created_at")
    elif qr_master:
        created_at = qr_master.get("created_at")
    else:
        first_link = assembly_processes_collection.find_one({"component_ids": qr_id}, sort=[("start_time", 1)])
        created_at = first_link.get("start_time") if first_link else None

    # ── Resolve part_id / part_name directly from qr_master (no extra queries) ─
    qr_part_id = qr_master.get("part_id") if qr_master else None
    part_name = "Unknown Part"
    if qr_part_id:
        part_doc = parts_collection.find_one({"part_id": qr_part_id}, {"name": 1})
        if part_doc:
            part_name = part_doc.get("name", "Unknown Part")

    product_info = {
        "qr_id": qr_id,
        "part_id": qr_part_id,
        "part_name": part_name,
        "created_at": created_at
    }

    job_card_entry = None
    if qr_master:
        job = job_cards_collection.find_one({"jobcard_id": qr_master.get("jobcard_id")})
        if job:
            job_card_entry = job.copy()
            job_card_entry.pop("_id", None)
            job_card_entry["type"] = "Job Card"

            # Back-fill creator info for older records
            if (not job_card_entry.get("created_by_name") or not job_card_entry.get("created_by_role") or not job_card_entry.get("created_by_department")) and job_card_entry.get("created_by"):
                creator = users_collection.find_one({"user_id": job_card_entry["created_by"]})
                if creator:
                    if not job_card_entry.get("created_by_name"):
                        job_card_entry["created_by_name"] = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
                    if not job_card_entry.get("created_by_role"):
                        job_card_entry["created_by_role"] = creator.get("role")
                    if not job_card_entry.get("created_by_department"):
                        job_card_entry["created_by_department"] = creator.get("department")

            variant_id = job_card_entry.get("variant_id")
            if variant_id and not job_card_entry.get("variant_sku"):
                variant = product_variants_collection.find_one({"variant_id": variant_id})
                if variant:
                    job_card_entry["variant_sku"]      = variant.get("sku_no")
                    job_card_entry["color"]            = variant.get("color")
                    job_card_entry["size"]             = variant.get("size")
                    job_card_entry["size_name"]        = variant.get("size_name")
                    job_card_entry["mrp"]              = variant.get("mrp")
                    job_card_entry["finish"]           = variant.get("finish")
                    job_card_entry["certification"]    = variant.get("certification")
                    job_card_entry["visor_type"]       = variant.get("visor_type")
                    job_card_entry["spoiler"]          = variant.get("spoiler")
                    job_card_entry["chinstrap_lock"]   = variant.get("chinstrap_lock")
                    job_card_entry["pinlock"]          = variant.get("pinlock")
                    job_card_entry["carton_box_size"]  = variant.get("carton_box_size")
                    job_card_entry["carton_barcode"]   = variant.get("carton_barcode")
                    submodel_id = variant.get("submodel_id")
                    if submodel_id and not job_card_entry.get("submodel_name"):
                        sub_doc = product_submodels_collection.find_one({"submodel_id": submodel_id})
                        if sub_doc:
                            job_card_entry.setdefault("submodel_id",   submodel_id)
                            job_card_entry.setdefault("submodel_name", sub_doc.get("name"))
                            model_id = sub_doc.get("model_id")
                            if model_id:
                                job_card_entry.setdefault("model_id", model_id)
                                model_doc = product_models_collection.find_one({"model_id": model_id})
                                if model_doc:
                                    job_card_entry.setdefault("model_name", model_doc.get("name"))
            if job_card_entry:
                product_info["model_name"] = job_card_entry.get("model_name")
                product_info["product_model_name"] = job_card_entry.get("product_model_name")
                if job_card_entry.get("product_model_name") and "product_model_name" not in job_card_entry:
                    job_card_entry["product_model_name"] = job_card_entry.get("product_model_name")


    scans = list(scanner_processes_collection.find({"qr_id": qr_id}))

    # ── Batch-resolve all scanner / inspector names in ONE query ──────────────
    user_ids_needed: set = set()
    for sp in scans:
        if not sp.get("scanner_name") and sp.get("scanner_id"):
            user_ids_needed.add(sp["scanner_id"])
        if sp.get("inspector_id") and not sp.get("inspector_name"):
            user_ids_needed.add(sp["inspector_id"])

    name_map: dict = {}
    if user_ids_needed:
        for u in users_collection.find(
            {"user_id": {"$in": list(user_ids_needed)}},
            {"user_id": 1, "first_name": 1, "last_name": 1}
        ):
            name_map[u["user_id"]] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()

    for sp in scans:
        sp.pop("_id", None)
        sp["type"] = "Reader Process"
        if not sp.get("scanner_name") and sp.get("scanner_id"):
            sp["scanner_name"] = name_map.get(sp["scanner_id"], "Unknown")
        if sp.get("inspector_id") and not sp.get("inspector_name"):
            sp["inspector_name"] = name_map.get(sp["inspector_id"], "Unknown")


    # ── Station jobcard enrichment ─────────────────────────────────────────────
    # station_jobcard_id is persisted on the scan record at scan time.
    # Read it directly — no FIFO computation needed.
    first_scan_for_jc: dict = {}
    for sp in scans:
        jcid = sp.get("station_jobcard_id")
        if jcid and jcid not in first_scan_for_jc:
            first_scan_for_jc[jcid] = sp

    # Bulk fetch all unique matched jobcard docs
    matched_jc_ids = list({
        sp["station_jobcard_id"]
        for sp in scans
        if sp.get("station_jobcard_id")
    })

    station_jc_entries = []
    if matched_jc_ids:
        jc_docs = {}
        for jc in job_cards_collection.find({"jobcard_id": {"$in": matched_jc_ids}}):
            jc.pop("_id", None)
            jc_docs[jc["jobcard_id"]] = jc

        creator_ids = list({
            jc.get("created_by")
            for jc in jc_docs.values()
            if jc.get("created_by") and not jc.get("created_by_name")
        })
        creator_map: dict = {}
        if creator_ids:
            for u in users_collection.find(
                {"user_id": {"$in": creator_ids}},
                {"user_id": 1, "first_name": 1, "last_name": 1, "role": 1, "department": 1}
            ):
                creator_map[u["user_id"]] = u

        seen_jc_ids: set = set()
        for sp in scans:
            jcid = sp.get("station_jobcard_id")
            if not jcid or jcid in seen_jc_ids:
                continue
            seen_jc_ids.add(jcid)
            jc_doc = jc_docs.get(jcid)
            if not jc_doc:
                continue
            jc_doc["type"] = "Job Card"

            # Enrich with process_name + station_name from the referencing scan
            ref_scan = first_scan_for_jc.get(jcid, {})
            if not jc_doc.get("process_name") and ref_scan.get("process_name"):
                jc_doc["process_name"] = ref_scan["process_name"]
            if not jc_doc.get("station_name") and ref_scan.get("station_name"):
                jc_doc["station_name"] = ref_scan["station_name"]
            if not jc_doc.get("station_id") and ref_scan.get("station_id"):
                jc_doc["station_id"] = ref_scan["station_id"]

            if not jc_doc.get("created_by_name"):
                u = creator_map.get(jc_doc.get("created_by", ""))
                if u:
                    jc_doc["created_by_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                    jc_doc.setdefault("created_by_role", u.get("role"))
                    jc_doc.setdefault("created_by_department", u.get("department"))
            station_jc_entries.append(jc_doc)

    scans.sort(key=lambda x: x["start_time"] if x.get("start_time") else datetime.min)

    if include_dispatch and product_info.get("part_name") and product_info["part_name"].upper() == "BOX":
        dispatch_data = _get_dispatch_tracking_logic(qr_id, recursive=False)
        if dispatch_data:
            scans.append({
                "type": "Dispatch Detail",
                "data": dispatch_data
            })

    return product_info, job_card_entry, scans, station_jc_entries




def _get_dispatch_tracking_logic(qr_id: str, recursive: bool = True):
    # 1. Find the dispatch record. 
    dispatch = dispatch_processes_collection.find_one({
        "$or": [
            {"dispatch_id": qr_id},
            {"qr_ids": qr_id}
        ]
    }, sort=[("start_time", -1)])
    
    if not dispatch:
        return None
        
    components = []
    seen_qrs = set()
    
    for qid in dispatch.get("qr_ids", []):
        if qid in seen_qrs: continue
        seen_qrs.add(qid)
        
        # Get individual data, but DO NOT recurse back into dispatch if we are already in one
        prod_info, job_card, scans, station_jc_entries = _get_qr_component_data(qid, include_dispatch=recursive)

        # Interleave station jobcards right before their first associated scan
        comp_history = []
        if job_card:
            comp_history.append(job_card)
        station_jc_map = {jc["jobcard_id"]: jc for jc in station_jc_entries if jc.get("jobcard_id")}
        inserted_station_jcs: set = set()
        for scan in scans:
            jcid = scan.get("station_jobcard_id")
            if jcid and jcid not in inserted_station_jcs and jcid in station_jc_map:
                comp_history.append(station_jc_map[jcid])
                inserted_station_jcs.add(jcid)
            comp_history.append(scan)
            
        components.append({
            "product": prod_info if prod_info else {"qr_id": qid, "part_name": get_part_name(qid)},
            "history": comp_history
        })

    dispatch.pop("_id", None)
    dispatch["type"] = "Dispatch Process"
    if not dispatch.get("linker_name"):
        dispatch["linker_name"] = get_name(dispatch.get("linker_id"))
    
    original_qr_ids = dispatch.get("qr_ids", [])
    dispatch["qr_ids"] = [{"qr_id": q, "part_name": get_part_name(q)} for q in original_qr_ids]
    
    return {
        "components": components,
        "dispatch_history": [dispatch]
    }

def _build_qr_history_tree(qr_id: str):
    
    visited_qrs = set()
    discovered_components = []
    discovered_assemblies = {} 

    def discover(qid):
        if not qid or qid in visited_qrs:
            return
        visited_qrs.add(qid)
        
        prod_info, job_card, scans, station_jc_entries = _get_qr_component_data(qid, include_dispatch=True)
        if not prod_info:
            discovered_components.append({
                "product": {"qr_id": qid, "part_name": f"ERROR: QR {qid} not found in master records"},
                "history": []
            })
            return

        # Build history: step-1 jobcard first, then scans in time order.
        # Station jobcards (step-2+) are inserted right before the first scan
        # that references them — so the order is:
        #   Job Card (step 1) → Reader Process → Job Card (step 2) → Reader Process → ...
        comp_history = []
        if job_card:
            comp_history.append(job_card)

        station_jc_map = {jc["jobcard_id"]: jc for jc in station_jc_entries if jc.get("jobcard_id")}
        inserted_station_jcs: set = set()
        for scan in scans:
            jcid = scan.get("station_jobcard_id")
            if jcid and jcid not in inserted_station_jcs and jcid in station_jc_map:
                comp_history.append(station_jc_map[jcid])
                inserted_station_jcs.add(jcid)
            comp_history.append(scan)

        discovered_components.append({
            "product": prod_info,
            "history": comp_history
        })
        assemblies = list(assembly_processes_collection.find({"component_ids": qid}))
        
        for ap in assemblies:
            asm_id = ap["assembly_id"]
            if asm_id not in discovered_assemblies:
                ap.pop("_id", None)
                ap["type"] = "Assembly Process"
                if not ap.get("linker_name"):
                    ap["linker_name"] = get_name(ap.get("linker_id"))
                if ap.get("inspector_id") and not ap.get("inspector_name"):
                    ap["inspector_name"] = get_name(ap.get("inspector_id"))
                
                original_qr_ids = ap.get("qr_ids", [])
                ap["qr_ids"] = _format_nested_qr_ids(original_qr_ids)
                
                discovered_assemblies[asm_id] = ap
                
                # Recurse for ALL QRs in this assembly
                all_qrs_in_asm = _flatten_qr_ids(original_qr_ids)
                for aqid in all_qrs_in_asm:
                    discover(aqid)

    discover(qr_id)
    
    if not discovered_components:
        return None
    asm_list = list(discovered_assemblies.values())
    asm_list.sort(key=lambda x: x["start_time"] if x.get("start_time") else datetime.min)
        
    return {
        "components": discovered_components,
        "assembly_history": asm_list
    }

@router.get("/history/{qr_id}", response_model=schemas.QRHistoryTree)
def get_qr_history(qr_id: str):
    tree = _build_qr_history_tree(qr_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Product / QR not found")
        
    return tree

@router.get("/dashboard-summary", response_model=schemas.DashboardSummary)
def get_dashboard_summary(current_user: dict = Depends(auth.get_current_user)):
    user_id = current_user["user_id"]
    role = current_user["role"]
    
    # 1. Determine filters based on role
    match_filter = {}
    asm_match_filter = {}
    jc_filter = {}
    
    if role == "Super Admin":
        # No filters - sees everything
        pass
    elif role == "Master Admin":
        sub_users = list(users_collection.find({"master_admin_id": user_id}, {"user_id": 1}))
        user_ids = [u["user_id"] for u in sub_users] + [user_id]
        
        # Primary filters by user scope
        match_filter["scanner_id"] = {"$in": user_ids}
        asm_match_filter["linker_id"] = {"$in": user_ids}
        jc_filter["created_by"] = user_id
        
        # Additional filter by part if assigned to Master Admin
        master_part_id = current_user.get("part_id")
        if master_part_id:
            # We need to filter scanner processes by part_id
            # scanner_processes_collection doesn't have part_id directly, but it's in qr_master
            # However, for efficiency, maybe we just filter the parts_summary later
            pass
    else:
        # Scanner, Linker, Inspector
        match_filter["scanner_id"] = user_id
        asm_match_filter["linker_id"] = user_id
        # Sub-users see job cards created by their Master Admin
        master_id = current_user.get("master_admin_id")
        if master_id:
            jc_filter["created_by"] = master_id

    # 2. Helper: Get Totals (Summary)
    def get_totals(m_filter, asm_filter):
        pipeline = [
            {"$match": m_filter},
            {"$group": {"_id": "$inspection_status", "count": {"$sum": 1}}}
        ]
        results = list(scanner_processes_collection.aggregate(pipeline))
        
        asm_pipeline = [
            {"$match": asm_filter},
            {"$group": {"_id": "$inspection_status", "count": {"$sum": 1}}}
        ]
        asm_results = list(assembly_processes_collection.aggregate(asm_pipeline))
        dsp_results = list(dispatch_processes_collection.aggregate(asm_pipeline))
        
        stats = {"OKAY": 0, "REWORKED": 0, "REJECTED": 0, "TOTAL": 0}
        for res in results + asm_results + dsp_results:
            status_key = res["_id"]
            if status_key in stats:
                stats[status_key] += res["count"]
            stats["TOTAL"] += res["count"]
        return stats

    # 3. Helper: Get Time-series Data
    def get_time_series(m_filter, asm_filter, days=7):
        now = utils.get_current_time()
        start_date = now - timedelta(days=days)
        
        m_filter_time = {**m_filter, "start_time": {"$gte": start_date}}
        asm_filter_time = {**asm_filter, "start_time": {"$gte": start_date}}
        
        group_format = "%Y-%m-%d"
        if days in [1, 0.5]:
            group_format = "%Y-%m-%d %H:00"
 
        pipeline = [
            {"$match": m_filter_time},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": group_format, "date": "$start_time"}},
                    "OKAY": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "OKAY"]}, 1, 0]}},
                    "REWORKED": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "REWORKED"]}, 1, 0]}},
                    "REJECTED": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "REJECTED"]}, 1, 0]}},
                    "TOTAL": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        scan_data = list(scanner_processes_collection.aggregate(pipeline))
        
        asm_pipeline = [
            {"$match": asm_filter_time},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": group_format, "date": "$start_time"}},
                    "OKAY": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "OKAY"]}, 1, 0]}},
                    "REWORKED": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "REWORKED"]}, 1, 0]}},
                    "REJECTED": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "REJECTED"]}, 1, 0]}},
                    "TOTAL": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        asm_data = list(assembly_processes_collection.aggregate(asm_pipeline))
        dsp_data = list(dispatch_processes_collection.aggregate(asm_pipeline))
        
        merged = {}
        # Pre-populate all expected hourly/daily slots to guarantee a complete time series
        if days == 1:
            for h in range(24):
                slot_time = now - timedelta(hours=h)
                key = slot_time.strftime("%Y-%m-%d %H:00")
                merged[key] = {"date": key, "OKAY": 0, "REWORKED": 0, "REJECTED": 0, "TOTAL": 0}
        elif days == 0.5:
            for h in range(12):
                slot_time = now - timedelta(hours=h)
                key = slot_time.strftime("%Y-%m-%d %H:00")
                merged[key] = {"date": key, "OKAY": 0, "REWORKED": 0, "REJECTED": 0, "TOTAL": 0}
        else:
            for d in range(days + 1):
                slot_time = now - timedelta(days=d)
                key = slot_time.strftime("%Y-%m-%d")
                merged[key] = {"date": key, "OKAY": 0, "REWORKED": 0, "REJECTED": 0, "TOTAL": 0}
 
        for entry in scan_data + asm_data + dsp_data:
            key = entry["_id"]
            if key not in merged:
                merged[key] = {"date": key, "OKAY": 0, "REWORKED": 0, "REJECTED": 0, "TOTAL": 0}
            merged[key]["OKAY"] += entry["OKAY"]
            merged[key]["REWORKED"] += entry["REWORKED"]
            merged[key]["REJECTED"] += entry["REJECTED"]
            merged[key]["TOTAL"] += entry["TOTAL"]
            
        return sorted(list(merged.values()), key=lambda x: x["date"])

    # 4. Helper: Get Part-wise Summary
    def get_parts_summary(m_filter):
        part_pipeline = [
            {"$match": m_filter},
            {
                "$lookup": {
                    "from": "qr_master",
                    "localField": "qr_id",
                    "foreignField": "qr_id",
                    "as": "qr_info"
                }
            },
            {
                "$addFields": {
                    "qr_info": {"$ifNull": [{"$arrayElemAt": ["$qr_info", 0]}, {}]}
                }
            },
            {
                "$lookup": {
                    "from": "parts",
                    "localField": "qr_info.part_id",
                    "foreignField": "part_id",
                    "as": "part_info"
                }
            },
            {"$unwind": "$part_info"},
            {
                "$group": {
                    "_id": "$part_info.name",
                    "OKAY": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "OKAY"]}, 1, 0]}},
                    "REWORKED": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "REWORKED"]}, 1, 0]}},
                    "REJECTED": {"$sum": {"$cond": [{"$eq": ["$inspection_status", "REJECTED"]}, 1, 0]}},
                    "TOTAL": {"$sum": 1}
                }
            },
            {"$sort": {"TOTAL": -1}}
        ]
        
        # If Master Admin has a specific part, filter the results to only that part
        if role == "Master Admin":
            master_part_id = current_user.get("part_id")
            if master_part_id:
                part = parts_collection.find_one({"part_id": master_part_id})
                if part:
                    part_name = part.get("name")
                    part_pipeline.append({"$match": {"_id": part_name}})
                    
        return list(scanner_processes_collection.aggregate(part_pipeline))

    # 5. Helper: Get Job Card Summary
    def get_job_cards_summary(filter_query):
        pipeline = [
            {"$match": filter_query},
            {"$group": {
                "_id": "$status", 
                "count": {"$sum": 1},
                "total_quantity": {"$sum": "$quantity"}
            }},
            {"$project": {"status": "$_id", "count": 1, "total_quantity": 1, "_id": 0}}
        ]
        results = list(job_cards_collection.aggregate(pipeline))
        total_qty = sum(item.get("total_quantity", 0) for item in results)
        return results, total_qty

    # 6. Compile Final Response
    jc_summary, jc_total_qty = get_job_cards_summary(jc_filter)
    
    return schemas.DashboardSummary(
        summary=get_totals(match_filter, asm_match_filter),
        time_series=schemas.DashboardTimeSeries(
            twelve_h=get_time_series(match_filter, asm_match_filter, days=0.5),
            twenty_four_h=get_time_series(match_filter, asm_match_filter, days=1),
            seven_d=get_time_series(match_filter, asm_match_filter, days=7),
            thirty_d=get_time_series(match_filter, asm_match_filter, days=30)
        ),
        total_linked=assembly_processes_collection.count_documents(asm_match_filter),
        parts_summary=get_parts_summary(match_filter),
        job_cards_summary=jc_summary,
        total_job_card_quantity=jc_total_qty
    )

@router.get("/user-history/{user_id}")
def get_user_history(
    user_id: str,
    current_user: dict = Depends(auth.get_current_user)
):
    return ScanOperations.get_user_history(user_id, current_user)

@router.get("/my-history")
def get_my_history(
    current_user: dict = Depends(auth.get_current_user)
):
    return ScanOperations.get_user_history(current_user["user_id"], current_user)

@router.get("/check/{qr_id}")
def check_qr(qr_id: str):
    return ScanOperations.check_qr(qr_id)

@router.get("/dispatch/{qr_id}")
def get_dispatch_tracking(qr_id: str):
    data = _get_dispatch_tracking_logic(qr_id, recursive=True)
    if not data:
        raise HTTPException(status_code=404, detail="Dispatch record not found")
    return data

def _check_and_update_job_card_completion(jobcard_id: str):
    import threading
    threading.Thread(
        target=_check_and_update_job_card_completion_sync,
        args=(jobcard_id,),
        daemon=True
    ).start()


def _trigger_station_fifo(station_id: str):
    """Trigger FIFO update for all station-based jobcards at this station (background)."""
    import threading
    threading.Thread(
        target=_update_station_jobcards_fifo,
        args=(station_id,),
        daemon=True
    ).start()


def _check_and_update_job_card_completion_sync(jobcard_id: str):
    if not jobcard_id:
        return

    job_card = job_cards_collection.find_one({"jobcard_id": jobcard_id})
    if not job_card:
        return

    quantity = job_card.get("quantity", 0)
    part_id = job_card.get("part_id")

    # ── Path A: step-1 jobcard — QRs are owned by this jobcard ──────────────
    qr_cursor = qr_master_collection.find({"jobcard_id": jobcard_id}, {"qr_id": 1})
    qr_ids = [q["qr_id"] for q in qr_cursor]

    if qr_ids:
        # Find the last step (maximum step number) for this part
        last_step_name = None
        if part_id:
            last_step_proc = processes_collection.find_one(
                {"part_id": part_id},
                sort=[("step", -1)]
            )
            if last_step_proc:
                last_step_name = last_step_proc.get("name")

        # Fast in-memory counting
        all_scans = list(scanner_processes_collection.find(
            {"qr_id": {"$in": qr_ids}},
            {"qr_id": 1, "process_name": 1, "inspection_status": 1, "start_time": 1, "_id": 0}
        ))
        all_asms = list(assembly_processes_collection.find(
            {"component_ids": {"$in": qr_ids}},
            {"component_ids": 1, "process_name": 1, "inspection_status": 1, "start_time": 1, "_id": 0}
        ))

        # Track latest record per QR
        latest_rec = {}
        for s in all_scans:
            qid = s.get("qr_id")
            st = s.get("start_time")
            if qid:
                if qid not in latest_rec or (st and (not latest_rec[qid].get("start_time") or st > latest_rec[qid]["start_time"])):
                    latest_rec[qid] = s
        for a in all_asms:
            st = a.get("start_time")
            for qid in a.get("component_ids", []):
                if qid not in latest_rec or (st and (not latest_rec[qid].get("start_time") or st > latest_rec[qid]["start_time"])):
                    latest_rec[qid] = a

        # Track OKAY at last step
        has_okay_last = set()
        for s in all_scans:
            if s.get("process_name") == last_step_name and s.get("inspection_status") == "OKAY":
                has_okay_last.add(s["qr_id"])
        for a in all_asms:
            if a.get("process_name") == last_step_name and a.get("inspection_status") == "OKAY":
                for qid in a.get("component_ids", []):
                    has_okay_last.add(qid)

        prod_statuses = {}
        for prod in products_collection.find({"qr_id": {"$in": qr_ids}}, {"qr_id": 1, "overall_status": 1, "_id": 0}):
            prod_statuses[prod["qr_id"]] = prod.get("overall_status")

        finished_count = 0
        for qid in qr_ids:
            latest = latest_rec.get(qid)
            if latest and latest.get("inspection_status") == "REJECTED":
                finished_count += 1
                continue
            if last_step_name:
                if qid in has_okay_last:
                    finished_count += 1
                    continue
            else:
                if latest and latest.get("inspection_status") == "OKAY" and latest.get("assembly_id"):
                    finished_count += 1
                    continue
            if prod_statuses.get(qid) in ["CYCLE COMPLETE", "DISPATCHED", "SCRAPPED"]:
                finished_count += 1

        from .job_card_api import JobCardOperations
        details = JobCardOperations.get_jobcard_completion_details(jobcard_id, quantity, part_id)

        update_fields = {
            "completion_percentage": details["completion_percentage"],
            "process_wise_completion": details["process_wise_completion"]
        }
        if finished_count >= quantity and quantity > 0:
            update_fields["status"] = "COMPLETED"
            update_rtdb(f"/job_cards/{jobcard_id}", {"status": "COMPLETED"})

        job_cards_collection.update_one({"jobcard_id": jobcard_id}, {"$set": update_fields})
        return

    # ── Path B: station-based jobcard — delegate to FIFO updater ────────────
    # Multiple jobcards can share the same station_ids. We must NOT update just
    # this one in isolation — that causes all of them to see the same total scan
    # count and all get marked completed at once. Instead, hand off to the FIFO
    # function which updates ALL jobcards at those stations in creation order.
    station_ids = job_card.get("station_ids") or []
    if not station_ids:
        return

    # FIFO updater handles all jobcards at these stations together
    for sid in station_ids:
        _update_station_jobcards_fifo(sid)


def _update_station_jobcards_fifo(station_id: str):
    """
    Time-windowed FIFO for station-based jobcards.

    Each jobcard owns scans in its own time window:
      [jobcard.created_at,  next_jobcard.created_at)
    The last jobcard's window is open-ended (up to now).

    This prevents old historical scans from instantly completing
    newly-created jobcards.
    """
    # 1. Station → process name
    station_doc = stations_collection.find_one(
        {"station_id": station_id},
        {"process": 1, "_id": 0}
    )
    if not station_doc:
        return
    process_name = station_doc.get("process")
    if not process_name:
        return

    # 2. All jobcards for this station, oldest first
    all_jcs = list(
        job_cards_collection.find(
            {"station_ids": station_id},
            {"jobcard_id": 1, "quantity": 1, "created_at": 1, "status": 1}
        ).sort("created_at", 1)
    )
    if not all_jcs:
        return
    all_okay_scans = list(
        scanner_processes_collection.find(
            {"station_id": station_id, "process_name": process_name, "inspection_status": "OKAY"},
            {"qr_id": 1, "start_time": 1, "_id": 0}
        ).sort("start_time", 1)
    )
    all_okay_asm = list(
        assembly_processes_collection.find(
            {"station_id": station_id, "process_name": process_name, "inspection_status": "OKAY"},
            {"component_ids": 1, "start_time": 1, "_id": 0}
        ).sort("start_time", 1)
    )

    # 4. For each jobcard count unique OKAY QRs within its time window
    active_set = False
    for idx, jc in enumerate(all_jcs):
        qty = jc.get("quantity") or 0
        if qty <= 0:
            continue

        window_start = jc.get("created_at")
        window_end = all_jcs[idx + 1].get("created_at") if idx + 1 < len(all_jcs) else None

        seen_qrs: set = set()
        for doc in all_okay_scans:
            t = doc.get("start_time")
            if t is None:
                continue
            if window_start and t < window_start:
                continue
            if window_end and t >= window_end:
                continue
            if doc.get("qr_id"):
                seen_qrs.add(doc["qr_id"])
        for doc in all_okay_asm:
            t = doc.get("start_time")
            if t is None:
                continue
            if window_start and t < window_start:
                continue
            if window_end and t >= window_end:
                continue
            for qid in doc.get("component_ids", []):
                seen_qrs.add(qid)

        finished = len(seen_qrs)
        pct = round((finished / qty) * 100, 2)

        update_fields = {"completion_percentage": pct}
        current_status = jc.get("status", "CREATED")

        if finished >= qty:
            # Slot fully filled → COMPLETED, deactivate
            if current_status != "COMPLETED":
                update_fields["status"] = "COMPLETED"
                update_rtdb(f"/job_cards/{jc['jobcard_id']}", {"status": "COMPLETED"})
            update_fields["is_active"] = False

        elif not active_set:
            # Currently filling slot — activate it; self-heal if wrongly completed
            if current_status == "COMPLETED":
                update_fields["status"] = "IN PROGRESS"
                update_rtdb(f"/job_cards/{jc['jobcard_id']}", {"status": "IN PROGRESS"})
            elif finished > 0 and current_status == "CREATED":
                update_fields["status"] = "IN PROGRESS"
                update_rtdb(f"/job_cards/{jc['jobcard_id']}", {"status": "IN PROGRESS"})
            update_fields["is_active"] = True
            active_set = True

        else:
            # Future slot — not yet active
            update_fields["is_active"] = False

        job_cards_collection.update_one(
            {"jobcard_id": jc["jobcard_id"]},
            {"$set": update_fields}
        )
