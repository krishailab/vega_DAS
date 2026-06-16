from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
import openpyxl
import io
import math
import re
from datetime import datetime
from pymongo.errors import BulkWriteError, DuplicateKeyError
import os
import urllib.request
import qrcode
import barcode
from barcode.writer import ImageWriter

from .. import schemas, auth, utils
from ..database import job_cards_collection, qr_master_collection, parts_collection, users_collection, product_variants_collection, product_models_collection, product_submodels_collection, product_brands_collection, product_subcategories_collection, product_categories_collection, scanner_processes_collection
from ..firebase_client import sync_job_card, sync_qr_master, sync_qr_masters_batch, update_rtdb, delete_from_rtdb, escape_firebase_key

# Imports for physical thermal label printing
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
import barcode
from barcode.writer import ImageWriter

router = APIRouter(prefix="/job-cards", tags=["Job Cards"])

class JobCardOperations:
    @staticmethod
    def get_jobcard_completion_details(jobcard_id: str, quantity: int, part_id: str = None) -> dict:
        if not jobcard_id or quantity <= 0:
            return {"completion_percentage": 0.0, "process_wise_completion": []}
            
        from ..database import (
            qr_master_collection,
            scanner_processes_collection,
            assembly_processes_collection,
            processes_collection,
            job_cards_collection
        )
            
        qr_cursor = qr_master_collection.find(
            {
                "$or": [
                    {"jobcard_id": jobcard_id},
                    {"linked_jobcards": jobcard_id}
                ]
            },
            {"qr_id": 1}
        )
        qr_ids = [q["qr_id"] for q in qr_cursor]
        if not qr_ids:
            return {"completion_percentage": 0.0, "process_wise_completion": []}
            
        jobcard = job_cards_collection.find_one({"jobcard_id": jobcard_id})
        specific_process_id = jobcard.get("process_id") if jobcard else None

        processes = []
        if specific_process_id:
            proc = processes_collection.find_one({"process_id": specific_process_id})
            if proc:
                processes = [proc]

        if part_id:
            processes = processes or list(processes_collection.find({"part_id": part_id}).sort("step", 1))
            
        # Fallback to a single default process if none defined
        if not processes:
            processes = [{
                "process_id": "default",
                "name": "Processing",
                "step": 1
            }]
            
        all_scans = list(scanner_processes_collection.find({"qr_id": {"$in": qr_ids}}))
        all_asms = list(assembly_processes_collection.find({"component_ids": {"$in": qr_ids}}))
        
        scans_by_qr = {}
        for s in all_scans:
            scans_by_qr.setdefault(s["qr_id"], []).append(s)
        asms_by_qr = {}
        for a in all_asms:
            for qid in a.get("component_ids", []):
                asms_by_qr.setdefault(qid, []).append(a)
                
        # Count completions
        total_completed_steps = 0
        process_completed_counts = {p["name"]: 0 for p in processes}
        
        for qid in qr_ids:
            qr_scans = scans_by_qr.get(qid, [])
            qr_asms = asms_by_qr.get(qid, [])
            
            # Determine if and where the QR was rejected
            rejected_step = None
            
            # Find if there's any rejected scan or assembly for this QR
            for s in qr_scans:
                if s.get("inspection_status") == "REJECTED":
                    step_num = 999
                    for p in processes:
                        if p["name"] == s.get("process_name"):
                            step_num = p.get("step") or 999
                            break
                    if rejected_step is None or step_num < rejected_step:
                        rejected_step = step_num
            for a in qr_asms:
                if a.get("inspection_status") == "REJECTED":
                    step_num = 999
                    for p in processes:
                        if p["name"] == a.get("process_name"):
                            step_num = p.get("step") or 999
                            break
                    if rejected_step is None or step_num < rejected_step:
                        rejected_step = step_num
            
            # For each process, check if the QR completed it
            for p in processes:
                p_name = p["name"]
                p_step = p.get("step") or 999
                
                # If rejected at a previous step, this step cannot be completed
                if rejected_step is not None and p_step > rejected_step:
                    continue
                
                # Check if QR has an OKAY record for this process
                # or if it was rejected at this exact process
                has_completed = False
                if rejected_step is not None and p_step == rejected_step:
                    has_completed = True
                else:
                    for s in qr_scans:
                        if s.get("process_name") == p_name and s.get("inspection_status") == "OKAY":
                            has_completed = True
                            break
                    if not has_completed:
                        for a in qr_asms:
                            if a.get("process_name") == p_name and a.get("inspection_status") == "OKAY":
                                has_completed = True
                                break
                                
                if has_completed:
                    process_completed_counts[p_name] += 1
                    total_completed_steps += 1
                    
        # Construct the process_wise_completion list
        process_wise_completion = []
        for p in processes:
            p_name = p["name"]
            completed_count = process_completed_counts[p_name]
            percentage = (completed_count / quantity) * 100 if quantity > 0 else 0.0
            process_wise_completion.append({
                "process_id": p.get("process_id") or "default",
                "process_name": p_name,
                "step": p.get("step") or 1,
                "completed_count": completed_count,
                "percentage": round(percentage, 2)
            })
            
        # Calculate overall completion percentage
        total_possible_steps = len(processes) * quantity
        overall_percentage = (total_completed_steps / total_possible_steps) * 100 if total_possible_steps > 0 else 0.0
        
        return {
            "completion_percentage": round(overall_percentage, 2),
            "process_wise_completion": process_wise_completion
        }

    @staticmethod
    def get_jobcard_completion_percentage(jobcard_id: str, quantity: int, part_id: str = None) -> float:
        details = JobCardOperations.get_jobcard_completion_details(jobcard_id, quantity, part_id)
        return details["completion_percentage"]

    @staticmethod
    def get_bulk_jobcard_completion_details(cards: list) -> dict:
        if not cards:
            return {}

        from ..database import (
            qr_master_collection,
            scanner_processes_collection,
            assembly_processes_collection,
            processes_collection
        )

        jobcard_ids = [c["jobcard_id"] for c in cards if c.get("jobcard_id")]
        if not jobcard_ids:
            return {}

        # 1. Fetch all QR codes matching either jobcard_id or linked_jobcards
        qr_cursor = qr_master_collection.find(
            {
                "$or": [
                    {"jobcard_id": {"$in": jobcard_ids}},
                    {"linked_jobcards": {"$in": jobcard_ids}}
                ]
            },
            {"qr_id": 1, "jobcard_id": 1, "linked_jobcards": 1}
        )

        # Map jobcard_id -> list of qr_ids
        jobcard_to_qrs = {jc_id: [] for jc_id in jobcard_ids}
        all_qr_ids = []

        for q in qr_cursor:
            qr_id = q.get("qr_id")
            if not qr_id:
                continue
            all_qr_ids.append(qr_id)

            jc_id = q.get("jobcard_id")
            if jc_id in jobcard_to_qrs:
                jobcard_to_qrs[jc_id].append(qr_id)

            linked = q.get("linked_jobcards")
            if isinstance(linked, list):
                for l_jc in linked:
                    if l_jc in jobcard_to_qrs:
                        jobcard_to_qrs[l_jc].append(qr_id)
            elif isinstance(linked, str) and linked in jobcard_to_qrs:
                jobcard_to_qrs[linked].append(qr_id)

        # 2. Fetch processes in bulk
        process_ids = list({c.get("process_id") for c in cards if c.get("process_id")})
        part_ids = list({c.get("part_id") for c in cards if c.get("part_id")})

        processes_map = {}
        if process_ids:
            for p in processes_collection.find({"process_id": {"$in": process_ids}}):
                processes_map[p["process_id"]] = p

        part_processes_map = {}
        if part_ids:
            for p in processes_collection.find({"part_id": {"$in": part_ids}}).sort("step", 1):
                part_processes_map.setdefault(p.get("part_id"), []).append(p)

        # 3. Fetch all scans and assemblies for all these QRs in bulk, filtering by relevant process names
        all_scans = []
        all_asms = []
        if all_qr_ids:
            # Collect all process names we are interested in to filter at the DB level
            process_names = set()
            for p in processes_map.values():
                if p.get("name"):
                    process_names.add(p["name"])
            for p_list in part_processes_map.values():
                for p in p_list:
                    if p.get("name"):
                        process_names.add(p["name"])
            
            scan_query = {"qr_id": {"$in": all_qr_ids}}
            asm_query = {"component_ids": {"$in": all_qr_ids}}
            
            if process_names:
                scan_query["process_name"] = {"$in": list(process_names)}
                asm_query["process_name"] = {"$in": list(process_names)}

            all_scans = list(scanner_processes_collection.find(
                scan_query,
                {"qr_id": 1, "process_name": 1, "inspection_status": 1, "_id": 0}
            ))
            all_asms = list(assembly_processes_collection.find(
                asm_query,
                {"component_ids": 1, "process_name": 1, "inspection_status": 1, "_id": 0}
            ))

        # Map (qr_id, process_name) -> inspection_status for O(1) lookups
        qr_process_status = {}
        for s in all_scans:
            qid = s.get("qr_id")
            pname = s.get("process_name")
            status = s.get("inspection_status")
            if qid and pname and status:
                # Keep latest status per process step
                qr_process_status[(qid, pname)] = status

        for a in all_asms:
            pname = a.get("process_name")
            status = a.get("inspection_status")
            if pname and status:
                for qid in a.get("component_ids", []):
                    qr_process_status[(qid, pname)] = status

        # 4. Compute completion details for each card
        bulk_details = {}
        for card in cards:
            jc_id = card.get("jobcard_id")
            quantity = card.get("quantity", 0)
            part_id = card.get("part_id")

            jc_qrs = jobcard_to_qrs.get(jc_id, [])
            if not jc_qrs or quantity <= 0:
                bulk_details[jc_id] = {"completion_percentage": 0.0, "process_wise_completion": []}
                continue

            specific_process_id = card.get("process_id")
            processes = []
            if specific_process_id:
                proc = processes_map.get(specific_process_id)
                if proc:
                    processes = [proc]

            if part_id:
                processes = processes or part_processes_map.get(part_id, [])

            if not processes:
                processes = [{
                    "process_id": "default",
                    "name": "Processing",
                    "step": 1
                }]

            total_completed_steps = 0
            process_completed_counts = {p["name"]: 0 for p in processes}

            for qid in jc_qrs:
                rejected_step = None
                for p in processes:
                    p_name = p["name"]
                    p_step = p.get("step") or 999
                    if qr_process_status.get((qid, p_name)) == "REJECTED":
                        if rejected_step is None or p_step < rejected_step:
                            rejected_step = p_step

                for p in processes:
                    p_name = p["name"]
                    p_step = p.get("step") or 999

                    if rejected_step is not None and p_step > rejected_step:
                        continue

                    has_completed = False
                    if rejected_step is not None and p_step == rejected_step:
                        has_completed = True
                    else:
                        if qr_process_status.get((qid, p_name)) == "OKAY":
                            has_completed = True

                    if has_completed:
                        process_completed_counts[p_name] += 1
                        total_completed_steps += 1

            process_wise_completion = []
            for p in processes:
                p_name = p["name"]
                completed_count = process_completed_counts[p_name]
                percentage = (completed_count / quantity) * 100 if quantity > 0 else 0.0
                process_wise_completion.append({
                    "process_id": p.get("process_id") or "default",
                    "process_name": p_name,
                    "step": p.get("step") or 1,
                    "completed_count": completed_count,
                    "percentage": round(percentage, 2)
                })

            total_possible_steps = len(processes) * quantity
            overall_percentage = (total_completed_steps / total_possible_steps) * 100 if total_possible_steps > 0 else 0.0

            bulk_details[jc_id] = {
                "completion_percentage": round(overall_percentage, 2),
                "process_wise_completion": process_wise_completion
            }

        return bulk_details


    @staticmethod
    def _generate_unique_jobcard_no() -> str:
        from ..database import job_cards_collection
        
        now = utils.get_current_time()
        prefix = now.strftime("%d%m%y") # e.g. "290526"
        
        regex = f"^{prefix}"
        today_cards = list(job_cards_collection.find({"jobcard_no": {"$regex": regex}}))
        max_seq = 0
        for card in today_cards:
            jc_no = card.get("jobcard_no", "")
            if len(jc_no) == 10:
                try:
                    seq = int(jc_no[6:])
                    if seq > max_seq:
                        max_seq = seq
                except ValueError:
                    pass
        next_seq = max_seq + 1
        
        while True:
            jobcard_no = f"{prefix}{next_seq:04d}"
            if not job_cards_collection.find_one({"jobcard_no": jobcard_no}):
                return jobcard_no
            next_seq += 1

    @staticmethod
    def _get_current_process_step(current_user: dict) -> int:
        from ..database import processes_collection

        process_step = 1
        if current_user.get("process_id"):
            process_doc = processes_collection.find_one({"process_id": current_user.get("process_id")})
            if process_doc and process_doc.get("step") is not None:
                process_step = process_doc.get("step")
        return process_step

    @staticmethod
    def _get_current_process_name(current_user: dict):
        if current_user.get("process_name"):
            return current_user.get("process_name")

        if current_user.get("process_id"):
            from ..database import processes_collection
            process_doc = processes_collection.find_one({"process_id": current_user.get("process_id")})
            if process_doc:
                return process_doc.get("name")
        return None

    @staticmethod
    def create_job_card(job_card: schemas.JobCardCreate, current_user: dict):
        # Use part_id from current_user profile
        part_id = current_user.get("part_id")
        if not part_id:
            raise HTTPException(status_code=400, detail="Master Admin has no part assigned in profile.")
            
        part = parts_collection.find_one({"part_id": part_id})
        if not part:
            raise HTTPException(status_code=404, detail="Assigned part not found in database.")
            
        jobcard_dict = job_card.model_dump() if hasattr(job_card, "model_dump") else job_card.dict()
        jobcard_dict["part_id"] = part_id
        jobcard_dict["part_model"] = part.get("name")
        jobcard_dict["plant_id"] = current_user.get("plant_id")
        jobcard_dict["process_id"] = current_user.get("process_id")
        jobcard_dict["process_name"] = JobCardOperations._get_current_process_name(current_user)
        jobcard_dict["created_by"] = current_user["user_id"]
        jobcard_dict["created_by_name"] = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        jobcard_dict["created_by_role"] = current_user.get("role")
        jobcard_dict["created_by_department"] = current_user.get("department")
        now = utils.get_current_time()
        jobcard_dict["created_at"] = now
        jobcard_dict["status"] = "CREATED"
        
        inserted = False
        attempts = 0
        while not inserted and attempts < 5:
            jobcard_no = job_card.jobcard_no
            if not jobcard_no:
                jobcard_no = JobCardOperations._generate_unique_jobcard_no()
            elif job_cards_collection.find_one({"jobcard_no": jobcard_no}):
                raise HTTPException(status_code=400, detail="Job Card number already exists")

            jobcard_dict["jobcard_no"] = jobcard_no
            jobcard_dict["jobcard_id"] = utils.generate_custom_id("JBC", job_cards_collection, "jobcard_id")

            try:
                job_cards_collection.insert_one(jobcard_dict)
                inserted = True
            except DuplicateKeyError:
                if job_card.jobcard_no:
                    raise HTTPException(status_code=400, detail="Job Card number already exists")
                jobcard_dict.pop("_id", None)
                attempts += 1
                if attempts >= 5:
                    raise HTTPException(status_code=409, detail="System busy. Failed to generate a unique Job Card number. Please try again.")

        jobcard_dict.pop("_id", None)
        sync_job_card(jobcard_dict)

        if JobCardOperations._get_current_process_step(current_user) == 1:
            # Run QR generation + DB insert in background so the API returns instantly
            import threading

            _jc_snapshot = dict(jobcard_dict)   # capture before any mutation
            _user_snapshot = dict(current_user)
            _quantity = job_card.quantity
            _auto_scan = bool(jobcard_dict.get("auto_scan"))

            def _bg_generate_qrs():
                import logging
                _log = logging.getLogger(__name__)

                part_name_bg = part.get("name", "PRODUCT")
                plant_id_bg = _user_snapshot.get("plant_id") or "PLT26AAAA0001"

                # Use a local `remaining` so we never reassign the closure-captured _quantity
                remaining = _quantity
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        qr_ids_bg = utils.generate_dynamic_product_qr_ids(
                            part_name_bg, plant_id_bg, remaining
                        )
                        now_bg = utils.get_current_time()
                        qr_records_bg = [
                            {
                                "qr_id": qr_id,
                                "jobcard_id": _jc_snapshot["jobcard_id"],
                                "part_id": _jc_snapshot["part_id"],
                                "master_admin_id": _user_snapshot["user_id"],
                                "status": "UNUSED",
                                "created_at": now_bg,
                            }
                            for qr_id in qr_ids_bg
                        ]

                        if qr_records_bg:
                            qr_master_collection.insert_many(qr_records_bg, ordered=False)
                            sync_qr_masters_batch(qr_records_bg)

                        if _auto_scan:
                            JobCardOperations._perform_auto_scan_for_jobcard(
                                _jc_snapshot, qr_ids_bg, _user_snapshot
                            )
                        return  # success

                    except BulkWriteError as bwe:
                        # Some QR IDs collided with a concurrent insert.
                        # Identify failed ones, sync the good ones, retry only the missing count.
                        write_errors = bwe.details.get("writeErrors", [])
                        failed_qr_ids = {
                            qr_records_bg[e["index"]]["qr_id"]
                            for e in write_errors
                            if e.get("code") == 11000  # duplicate key
                        }
                        _log.warning(
                            "Jobcard %s QR generation attempt %d: %d duplicates — retrying %d",
                            _jc_snapshot.get("jobcard_id"), attempt + 1,
                            len(failed_qr_ids), len(failed_qr_ids)
                        )
                        good_records = [r for r in qr_records_bg if r["qr_id"] not in failed_qr_ids]
                        if good_records:
                            sync_qr_masters_batch(good_records)

                        remaining = len(failed_qr_ids)  # only re-generate what's missing
                        if attempt == max_retries - 1:
                            _log.error(
                                "Jobcard %s: QR generation failed after %d attempts (%d QRs missing)",
                                _jc_snapshot.get("jobcard_id"), max_retries, remaining
                            )

                    except Exception:
                        _log.exception(
                            "Background QR generation failed for jobcard %s (attempt %d)",
                            _jc_snapshot.get("jobcard_id"), attempt + 1
                        )
                        return

            threading.Thread(target=_bg_generate_qrs, daemon=True).start()

        return jobcard_dict

    @staticmethod
    def _perform_auto_scan_for_jobcard(jobcard_dict: dict, qr_ids: list, current_user: dict):
        if not jobcard_dict.get("auto_scan") or not jobcard_dict.get("station_ids") or not qr_ids:
            return
            
        import threading
        
        def _bg_scan():
            from ..database import (
                stations_collection,
                scanner_processes_collection,
                products_collection,
                assembly_processes_collection,
                parts_collection,
                qr_master_collection,
                job_cards_collection
            )
            from ..firebase_client import sync_scan, sync_product, update_rtdb
            from .scan_api import _check_and_update_job_card_completion
            
            now = utils.get_current_time()
            station_ids = jobcard_dict["station_ids"]
            
            stations = list(stations_collection.find({"station_id": {"$in": station_ids}}))
            station_map = {s["station_id"]: s for s in stations}
            ordered_stations = [station_map[sid] for sid in station_ids if sid in station_map]
            
            part_id = jobcard_dict.get("part_id")
            part = parts_collection.find_one({"part_id": part_id}) if part_id else None
            part_name = part.get("name", "Unknown Part") if part else "Unknown Part"
            
            # Mark job card as IN PROGRESS
            job_cards_collection.update_one(
                {"jobcard_id": jobcard_dict["jobcard_id"]},
                {"$set": {"status": "IN PROGRESS"}}
            )
            update_rtdb(f"/job_cards/{jobcard_dict['jobcard_id']}", {"status": "IN PROGRESS"})
            jobcard_dict["status"] = "IN PROGRESS"
            
            for qr_id in qr_ids:
                product = products_collection.find_one({"qr_id": qr_id})
                if not product:
                    product_doc = {
                        "qr_id": qr_id,
                        "master_admin_id": current_user["user_id"],
                        "overall_status": "WIP",
                        "created_at": now
                    }
                    products_collection.insert_one(product_doc)
                    sync_product(product_doc)
                    
                qr_master_collection.update_one(
                    {"qr_id": qr_id},
                    {"$set": {"status": "IN USE"}}
                )
                update_rtdb(f"/qr_master/{qr_id}", {"status": "IN USE"})
                
                for station in ordered_stations:
                    process_name = station.get("process", "Unknown Process")
                    
                    scanner_processes_collection.update_many({"qr_id": qr_id}, {"$set": {"is_latest": False}})
                    assembly_processes_collection.update_many({"qr_ids": qr_id}, {"$set": {"is_latest": False}})
                    
                    scan_dict = {
                        "scan_id": utils.generate_custom_id("SCN", scanner_processes_collection, "scan_id"),
                        "qr_id": qr_id,
                        "process_name": process_name,
                        "part_name": part_name,
                        "station_name": station.get("name", "Unknown Station"),
                        "station_comment": station.get("comment"),
                        "station_id": station.get("station_id"),
                        "scanner_id": "AUTO",
                        "scanner_name": "AUTO",
                        "inspection_status": "OKAY",
                        "is_latest": True,
                        "start_time": now,
                        "end_time": None,
                        "inspector_id": None,
                        "reject_reason": None,
                        "plant_id": station.get("plant_id") or current_user.get("plant_id"),
                        "plant_name": station.get("plant_name") or current_user.get("plant_name"),
                        "plant_address": station.get("plant_address") or current_user.get("plant_address"),
                    }
                    
                    scanner_processes_collection.insert_one(scan_dict)
                    scan_dict.pop("_id", None)
                    sync_scan(scan_dict)
                    
            # Mark job card as COMPLETED since all requested station scans are completed
            job_cards_collection.update_one(
                {"jobcard_id": jobcard_dict["jobcard_id"]},
                {"$set": {"status": "COMPLETED"}}
            )
            update_rtdb(f"/job_cards/{jobcard_dict['jobcard_id']}", {"status": "COMPLETED"})
            jobcard_dict["status"] = "COMPLETED"
                    
            _check_and_update_job_card_completion(jobcard_dict["jobcard_id"])

        threading.Thread(target=_bg_scan, daemon=True).start()

    @staticmethod
    def _enrich_variant_fields(card: dict) -> dict:
        """Back-fill variant attributes for a SINGLE card (used by write paths)."""
        variant = None
        if card.get("variant_id"):
            variant = product_variants_collection.find_one({"variant_id": card["variant_id"]})
        elif card.get("variant_sku"):
            variant = product_variants_collection.find_one({"sku_no": card["variant_sku"]})
            
        if not variant:
            return card
            
        card.setdefault("variant_sku", variant.get("sku_no"))
        card.setdefault("size", variant.get("size"))
        card.setdefault("size_name", variant.get("size_name"))
        
        # Fetch parent submodel hierarchy
        submodel_id = variant.get("submodel_id")
        submodel_doc = None
        if submodel_id:
            submodel_doc = product_submodels_collection.find_one({"submodel_id": submodel_id})
            if submodel_doc:
                card.setdefault("submodel_id", submodel_id)
                card.setdefault("submodel_name", submodel_doc.get("name"))
                card.setdefault("submodel_image", submodel_doc.get("image"))
                card.setdefault("box_weight", submodel_doc.get("box_weight"))
                card.setdefault("box_dimension", submodel_doc.get("box_dimension"))
                card.setdefault("carton_weight", submodel_doc.get("carton_weight"))
                card.setdefault("carton_dimension", submodel_doc.get("carton_dimension"))
                model_id = submodel_doc.get("model_id")
                if model_id:
                    card.setdefault("model_id", model_id)
                    model_doc = product_models_collection.find_one({"model_id": model_id})
                    if model_doc:
                        card.setdefault("model_name", model_doc.get("name"))
                        # Fetch brand logo from the brand linked to the model
                        brand_id = model_doc.get("brand_id")
                        if brand_id:
                            brand_doc = product_brands_collection.find_one({"brand_id": brand_id})
                            if brand_doc:
                                card.setdefault("brand_name", brand_doc.get("name"))
                                card.setdefault("brand_logo_url", brand_doc.get("logo_url"))

        def get_field(field_name, default=None):
            val = variant.get(field_name)
            if val is None and submodel_doc:
                val = submodel_doc.get(field_name)
            return val if val is not None else default

        card.setdefault("color", get_field("color"))
        card.setdefault("mrp", get_field("mrp"))
        card.setdefault("finish", get_field("finish"))
        card.setdefault("certification", get_field("certification"))
        card.setdefault("visor_type", get_field("visor_type"))
        card.setdefault("spoiler", get_field("spoiler"))
        card.setdefault("chinstrap_lock", get_field("chinstrap_lock"))
        card.setdefault("pinlock", get_field("pinlock"))
        card.setdefault("carton_box_size", get_field("carton_box_size"))
        card.setdefault("carton_barcode", get_field("carton_barcode"))
        card.setdefault("product_images", get_field("product_images", []))
        return card

    @staticmethod
    def _enrich_cards_batch(cards: list) -> None:
        """
        Populate variant / hierarchy / creator fields for a list of cards
        using BATCH queries (one $in query per collection instead of N find_one calls).
        Mutates cards in-place; returns nothing.
        """
        if not cards:
            return
        creator_ids = list({
            c["created_by"] for c in cards
            if c.get("created_by") and (
                not c.get("created_by_name")
                or not c.get("created_by_role")
                or not c.get("created_by_department")
            )
        })
        users_map = {}
        if creator_ids:
            for u in users_collection.find(
                {"user_id": {"$in": creator_ids}},
                {"user_id": 1, "first_name": 1, "last_name": 1, "role": 1, "department": 1}
            ):
                users_map[u["user_id"]] = u

        for c in cards:
            uid = c.get("created_by")
            if uid and uid in users_map:
                u = users_map[uid]
                if not c.get("created_by_name"):
                    c["created_by_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                if not c.get("created_by_role"):
                    c["created_by_role"] = u.get("role")
                if not c.get("created_by_department"):
                    c["created_by_department"] = u.get("department")

        # ── 2. Variants ──────────────────────────────────────────────────
        variant_ids = list({c["variant_id"] for c in cards if c.get("variant_id")})
        variant_skus = list({
            c["variant_sku"] for c in cards
            if not c.get("variant_id") and c.get("variant_sku")
        })
        variants_map = {}  # keyed by variant_id
        if variant_ids:
            for v in product_variants_collection.find({"variant_id": {"$in": variant_ids}}):
                variants_map[v["variant_id"]] = v
        if variant_skus:
            for v in product_variants_collection.find({"sku_no": {"$in": variant_skus}}):
                variants_map.setdefault(v["variant_id"], v)  # avoid dups

        # Build a card→variant mapping
        card_variant = {}
        for c in cards:
            if c.get("variant_id") and c["variant_id"] in variants_map:
                card_variant[id(c)] = variants_map[c["variant_id"]]
            elif c.get("variant_sku"):
                for v in variants_map.values():
                    if v.get("sku_no") == c["variant_sku"]:
                        card_variant[id(c)] = v
                        break

        # ── 3. Submodels ─────────────────────────────────────────────────
        submodel_ids = list({
            card_variant[id(c)].get("submodel_id")
            for c in cards
            if id(c) in card_variant and card_variant[id(c)].get("submodel_id")
        })
        submodels_map = {}
        if submodel_ids:
            for sm in product_submodels_collection.find({"submodel_id": {"$in": submodel_ids}}):
                submodels_map[sm["submodel_id"]] = sm

        # Enrich variant fields with submodel fallbacks and submodel fields
        submodel_fields = [
            "name", "image", "box_weight", "box_dimension",
            "carton_weight", "carton_dimension",
        ]
        card_submodel = {}
        for c in cards:
            v = card_variant.get(id(c))
            if not v:
                continue
            sm_id = v.get("submodel_id")
            sm = submodels_map.get(sm_id) if sm_id else None

            c.setdefault("variant_sku", v.get("sku_no"))
            c.setdefault("size", v.get("size"))
            c.setdefault("size_name", v.get("size_name"))

            def get_field_val(f_name, default=None):
                val = v.get(f_name)
                if val is None and sm:
                    val = sm.get(f_name)
                return val if val is not None else default

            c.setdefault("color", get_field_val("color"))
            c.setdefault("mrp", get_field_val("mrp"))
            c.setdefault("finish", get_field_val("finish"))
            c.setdefault("certification", get_field_val("certification"))
            c.setdefault("visor_type", get_field_val("visor_type"))
            c.setdefault("spoiler", get_field_val("spoiler"))
            c.setdefault("chinstrap_lock", get_field_val("chinstrap_lock"))
            c.setdefault("pinlock", get_field_val("pinlock"))
            c.setdefault("carton_box_size", get_field_val("carton_box_size"))
            c.setdefault("carton_barcode", get_field_val("carton_barcode"))
            c.setdefault("product_images", get_field_val("product_images", []))

            if sm:
                card_submodel[id(c)] = sm
                c.setdefault("submodel_id", sm_id)
                c.setdefault("submodel_name", sm.get("name"))
                c.setdefault("submodel_image", sm.get("image"))
                for f in submodel_fields[2:]:
                    c.setdefault(f, sm.get(f))

        # ── 4. Models ────────────────────────────────────────────────────
        model_ids = list({
            card_submodel[id(c)].get("model_id")
            for c in cards
            if id(c) in card_submodel and card_submodel[id(c)].get("model_id")
        })
        models_map = {}
        if model_ids:
            for m in product_models_collection.find({"model_id": {"$in": model_ids}}):
                models_map[m["model_id"]] = m

        card_model = {}
        for c in cards:
            sm = card_submodel.get(id(c))
            if not sm:
                continue
            m_id = sm.get("model_id")
            if m_id and m_id in models_map:
                m = models_map[m_id]
                card_model[id(c)] = m
                c.setdefault("model_id", m_id)
                c.setdefault("model_name", m.get("name"))

        # ── 5. Brands ────────────────────────────────────────────────────
        brand_ids = list({
            card_model[id(c)].get("brand_id")
            for c in cards
            if id(c) in card_model and card_model[id(c)].get("brand_id")
        })
        brands_map = {}
        if brand_ids:
            for b in product_brands_collection.find({"brand_id": {"$in": brand_ids}}):
                brands_map[b["brand_id"]] = b

        for c in cards:
            m = card_model.get(id(c))
            if not m:
                continue
            b_id = m.get("brand_id")
            if b_id and b_id in brands_map:
                b = brands_map[b_id]
                c.setdefault("brand_name", b.get("name"))
                c.setdefault("brand_logo_url", b.get("logo_url"))

    @staticmethod
    def _enrich_completion_batch(cards: list) -> None:
        """
        Mock completion percentage and process-wise completion fields to
        completely eliminate lookup bottlenecks on GET paths.
        """
        for c in cards:
            c["completion_percentage"] = 0.0
            c["process_wise_completion"] = []

    @staticmethod
    def get_job_cards(current_user: dict, page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if current_user.get("role") != "Super Admin":
            plant_id = current_user.get("plant_id")
            process_id = current_user.get("process_id")
            if plant_id and process_id:
                query = {"plant_id": plant_id, "process_id": process_id}
            else:
                query["created_by"] = current_user["user_id"]

        if search:
            search_filter = [
                {"jobcard_no": {"$regex": search, "$options": "i"}},
                {"jobcard_id": {"$regex": search, "$options": "i"}},
                {"part_model": {"$regex": search, "$options": "i"}},
                {"variant_sku": {"$regex": search, "$options": "i"}},
                {"color": {"$regex": search, "$options": "i"}},
                {"size_name": {"$regex": search, "$options": "i"}}
            ]
            if "$or" in query:
                query = {"$and": [query, {"$or": search_filter}]}
            else:
                query["$or"] = search_filter

        # Get total matching document count for total pages calculation
        total_count = job_cards_collection.count_documents(query)
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0

        skip = (page - 1) * limit
        # Sort in reverse chronological order (-1 on created_at or jobcard_id/jobcard_no)
        cards = list(job_cards_collection.find(query).sort("created_at", -1).skip(skip).limit(limit))

        # 1. Batch fetch user creators
        creator_ids = list({
            c["created_by"] for c in cards 
            if c.get("created_by") and (not c.get("created_by_name") or not c.get("created_by_role") or not c.get("created_by_department"))
        })
        user_map = {}
        if creator_ids:
            for u in users_collection.find({"user_id": {"$in": creator_ids}}):
                user_map[u["user_id"]] = u

        for c in cards:
            c.pop("_id", None)
            
            # Map creators
            if (not c.get("created_by_name") or not c.get("created_by_role") or not c.get("created_by_department")) and c.get("created_by"):
                creator = user_map.get(c["created_by"])
                if creator:
                    if not c.get("created_by_name"):
                        c["created_by_name"] = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
                    if not c.get("created_by_role"):
                        c["created_by_role"] = creator.get("role")
                    if not c.get("created_by_department"):
                        c["created_by_department"] = creator.get("department")

            JobCardOperations._enrich_variant_fields(c)
            
            # Map completion details directly from DB fields
            c["completion_percentage"] = c.get("completion_percentage", 0.0)
            c["process_wise_completion"] = c.get("process_wise_completion", [])

        return {
            "cards": cards,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def delete_job_card(jobcard_id: str, current_user: dict):
        plant_id = current_user.get("plant_id")
        process_id = current_user.get("process_id")
        query = {"jobcard_id": jobcard_id}
        if current_user.get("role") != "Super Admin":
            if plant_id and process_id:
                query["$or"] = [
                    {"created_by": current_user["user_id"]},
                    {"plant_id": plant_id, "process_id": process_id}
                ]
            else:
                query["created_by"] = current_user["user_id"]
        existing = job_cards_collection.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Job Card not found")

        jc_status = str(existing.get("status", "")).strip().upper()
        if jc_status in ["IN PROGRESS", "COMPLETED"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Job Card cannot be deleted when its status is In Progress or Completed (current status: {existing.get('status')})"
            )
            
        # 1. Get associated QR codes
        qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id}))
        qr_ids = [q.get("qr_id") for q in qrs if q.get("qr_id")]
        
        # 2. Delete scanner processes and QR codes
        if qr_ids:
            scanner_processes_collection.delete_many({"qr_id": {"$in": qr_ids}})
            qr_master_collection.delete_many({"jobcard_id": jobcard_id})
            
        # 3. Delete job card itself
        job_cards_collection.delete_one({"jobcard_id": jobcard_id})

        # 4. Clean up Firebase in background — don't block the HTTP response
        #    (per-QR delete loop was doing one HTTP call per QR synchronously)
        import threading

        _qr_ids_snapshot = list(qr_ids)
        _jobcard_id_snapshot = jobcard_id

        def _bg_firebase_cleanup():
            delete_from_rtdb(f"/job_cards/{_jobcard_id_snapshot}")
            for qr_id in _qr_ids_snapshot:
                delete_from_rtdb(f"/qr_master/{escape_firebase_key(qr_id)}")

        threading.Thread(target=_bg_firebase_cleanup, daemon=True).start()

        return {"detail": "Job Card and all associated QR codes/scans deleted successfully"}

    @staticmethod
    def download_qrs(jobcard_id: str, current_user: dict):
        plant_id = current_user.get("plant_id")
        process_id = current_user.get("process_id")
        query = {"jobcard_id": jobcard_id}
        if current_user.get("role") != "Super Admin":
            if plant_id and process_id:
                query["$or"] = [
                    {"created_by": current_user["user_id"]},
                    {"plant_id": plant_id, "process_id": process_id}
                ]
            else:
                query["created_by"] = current_user["user_id"]
                
        job_card = job_cards_collection.find_one(query)
        if not job_card:
            raise HTTPException(status_code=404, detail="Job Card not found")
            
        qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id}, {"qr_id": 1, "_id": 0}))
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "QR Codes"
        
        ws.append(["Product ID"])
        for qr in qrs:
            ws.append([qr["qr_id"]])
            
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        headers = {
            'Content-Disposition': f'attachment; filename="jobcard_{jobcard_id}_qrs.xlsx"'
        }
        
        return StreamingResponse(buffer, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)

    @staticmethod
    def get_job_card(jobcard_id: str, current_user: dict):
        plant_id = current_user.get("plant_id")
        process_id = current_user.get("process_id")
        query = {"jobcard_id": jobcard_id}
        if current_user.get("role") != "Super Admin":
            if plant_id and process_id:
                query["$or"] = [
                    {"created_by": current_user["user_id"]},
                    {"plant_id": plant_id, "process_id": process_id}
                ]
            else:
                query["created_by"] = current_user["user_id"]
                
        card = job_cards_collection.find_one(query)
        if not card:
            raise HTTPException(status_code=404, detail="Job Card not found")
        card.pop("_id", None)
        JobCardOperations._enrich_variant_fields(card)
        
        # Read pre-calculated fields directly, falling back only if they do not exist
        if "completion_percentage" in card:
            card["completion_percentage"] = card.get("completion_percentage", 0.0)
            card["process_wise_completion"] = card.get("process_wise_completion", [])
        else:
            details = JobCardOperations.get_jobcard_completion_details(card["jobcard_id"], card["quantity"], card.get("part_id"))
            card["completion_percentage"] = details["completion_percentage"]
            card["process_wise_completion"] = details["process_wise_completion"]
        return card

    @staticmethod
    def update_job_card_status(jobcard_id: str, status_update: schemas.JobCardStatusUpdate, current_user: dict):
        plant_id = current_user.get("plant_id")
        process_id = current_user.get("process_id")
        query = {"jobcard_id": jobcard_id}
        if current_user.get("role") != "Super Admin":
            if plant_id and process_id:
                query["$or"] = [
                    {"created_by": current_user["user_id"]},
                    {"plant_id": plant_id, "process_id": process_id}
                ]
            else:
                query["created_by"] = current_user["user_id"]
                
        result = job_cards_collection.update_one(
            query,
            {"$set": {"status": status_update.status}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Job Card not found")
        update_rtdb(f"/job_cards/{jobcard_id}", {"status": status_update.status})
        return {"detail": "Job Card status updated successfully"}

    @staticmethod
    def preview_reverse_import(file: UploadFile, current_user: dict):
        if not file.filename.endswith('.xlsx'):
            raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
            
        try:
            contents = file.file.read()
            wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True)
            ws = wb.active
            
            product_ids = []
            qr_ids = []
            
            # Expected header: Product ID (or just column 1)
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not any(row): continue
                
                qr_id = row[0]
                if not qr_id: continue
                
                qr_ids.append(str(qr_id).strip())
                
            # Perform a single bulk query to check for existing QR codes
            existing_cursor = qr_master_collection.find(
                {"qr_id": {"$in": qr_ids}},
                {"qr_id": 1, "jobcard_id": 1}
            )
            existing_map = {doc["qr_id"]: doc.get("jobcard_id") for doc in existing_cursor}
            
            for qr_id in qr_ids:
                linked_jobcard = existing_map.get(qr_id)
                if linked_jobcard:
                    is_valid = False
                    error = f"Product ID {qr_id} is already linked to Job Card {linked_jobcard}"
                else:
                    is_valid = True
                    error = None
                
                product_ids.append({
                    "qr_id": qr_id,
                    "is_valid": is_valid,
                    "error": error
                })
                
            return product_ids
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

    @staticmethod
    def create_reverse_job_card(data: schemas.JobCardReverseCreate, current_user: dict):
        jobcard_no = data.jobcard_no
        if not jobcard_no:
            jobcard_no = JobCardOperations._generate_unique_jobcard_no()
        else:
            if job_cards_collection.find_one({"jobcard_no": jobcard_no}):
                raise HTTPException(status_code=400, detail="Job Card number already exists")
            
        # Validate variant exists if variant_sku is provided
        variant = None
        if data.variant_sku:
            variant = product_variants_collection.find_one({"sku_no": data.variant_sku})
            if not variant:
                raise HTTPException(status_code=404, detail="Product variant not found")
            
        # Use part_id from current_user profile
        part_id = current_user.get("part_id")
        if not part_id:
            raise HTTPException(status_code=400, detail="Master Admin has no part assigned.")
            
        part = parts_collection.find_one({"part_id": part_id})
        
        jobcard_dict = {
            "jobcard_no": jobcard_no,
            "jobcard_date": data.jobcard_date,
            "part_composition": data.part_composition,
            "quantity": len(data.qr_ids),
            "station_ids": getattr(data, "station_ids", []),
            "part_id": part_id,
            "part_model": part.get("name") if part else "Unknown",
            "plant_id": current_user.get("plant_id"),
            "process_id": current_user.get("process_id"),
            "process_name": JobCardOperations._get_current_process_name(current_user),
            "jobcard_id": utils.generate_custom_id("JBC", job_cards_collection, "jobcard_id"),
            "created_by": current_user["user_id"],
            "created_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
            "created_by_role": current_user.get("role"),
            "created_by_department": current_user.get("department"),
            "created_at": utils.get_current_time(),
            "status": "CREATED",
            "product_model_name": data.product_model_name,
            "auto_scan": getattr(data, "auto_scan", False)
        }
        _station_ids = getattr(data, "station_ids", []) or []
        if _station_ids:
            _already_active = job_cards_collection.find_one(
                {"station_ids": {"$in": _station_ids}, "is_active": True},
                {"jobcard_id": 1}
            )
            jobcard_dict["is_active"] = not bool(_already_active)
        else:
            jobcard_dict["is_active"] = False
        if variant:
            jobcard_dict["variant_id"] = variant.get("variant_id")
            jobcard_dict["variant_sku"] = variant.get("sku_no")
            
        job_cards_collection.insert_one(jobcard_dict)
        jobcard_dict.pop("_id", None)
        sync_job_card(jobcard_dict)
        
        # Link existing/provided QR IDs
        now = utils.get_current_time()
        qr_records_to_insert = []
        for qr_id in data.qr_ids:
            existing_qr = qr_master_collection.find_one({"qr_id": qr_id})
            if existing_qr:
                qr_master_collection.update_one(
                    {"qr_id": qr_id},
                    {"$set": {
                        "jobcard_id": jobcard_dict["jobcard_id"],
                        "part_id": part_id,
                        "master_admin_id": current_user["user_id"],
                        "status": "UNUSED" # Reset status if linking to new jobcard
                    }}
                )
                update_rtdb(f"/qr_master/{qr_id}", {
                    "jobcard_id": jobcard_dict["jobcard_id"],
                    "part_id": part_id,
                    "master_admin_id": current_user["user_id"],
                    "status": "UNUSED"
                })
            else:
                qr_records_to_insert.append({
                    "qr_id": qr_id,
                    "jobcard_id": jobcard_dict["jobcard_id"],
                    "part_id": part_id,
                    "master_admin_id": current_user["user_id"],
                    "status": "UNUSED",
                    "created_at": now
                })
        
        if qr_records_to_insert:
            qr_master_collection.insert_many(qr_records_to_insert)
            sync_qr_masters_batch(qr_records_to_insert)
            
        JobCardOperations._perform_auto_scan_for_jobcard(jobcard_dict, data.qr_ids, current_user)
            
        if variant:
            JobCardOperations._enrich_variant_fields(jobcard_dict)
            
        return jobcard_dict
    @staticmethod
    def create_assemble_job_card(job_card: schemas.JobCardCreate, variant_sku: str, current_user: dict):
        if job_card.jobcard_no and job_cards_collection.find_one({"jobcard_no": job_card.jobcard_no}):
            raise HTTPException(status_code=400, detail="Job Card number already exists")

        # Validate variant exists
        variant = product_variants_collection.find_one({"sku_no": variant_sku})
        if not variant:
            raise HTTPException(status_code=404, detail="Product variant not found")
        # Use part_id from current_user profile
        part_id = current_user.get("part_id")
        if not part_id:
            raise HTTPException(status_code=400, detail="Master Admin has no part assigned.")
        part = parts_collection.find_one({"part_id": part_id})
        if not part:
            raise HTTPException(status_code=404, detail="Assigned part not found in database.")
        # (Model and submodel hierarchy is now fetched dynamically via _enrich_variant_fields)
 
        # Build job card document
        jobcard_dict = {
            "jobcard_date": job_card.jobcard_date,
            "part_composition": job_card.part_composition,
            "quantity": job_card.quantity,
            "station_ids": getattr(job_card, "station_ids", []),
            "part_id": part_id,
            "part_model": part.get("name") if part else "Unknown",
            "variant_id": variant.get("variant_id"),
            "variant_sku": variant.get("sku_no"),
            "plant_id": current_user.get("plant_id"),
            "process_id": current_user.get("process_id"),
            "process_name": JobCardOperations._get_current_process_name(current_user),
            "created_by": current_user["user_id"],
            "created_by_name": (f"{current_user.get('first_name','')} {current_user.get('last_name','')}").strip(),
            "created_by_role": current_user.get("role"),
            "created_by_department": current_user.get("department"),
            "created_at": utils.get_current_time(),
            "status": "CREATED",
            "product_model_name": job_card.product_model_name,
            "currency": getattr(job_card, "currency", "INR"),
            "auto_scan": getattr(job_card, "auto_scan", False)
        }
        _station_ids = getattr(job_card, "station_ids", []) or []
        if _station_ids:
            _already_active = job_cards_collection.find_one(
                {"station_ids": {"$in": _station_ids}, "is_active": True},
                {"jobcard_id": 1}
            )
            jobcard_dict["is_active"] = not bool(_already_active)
        else:
            jobcard_dict["is_active"] = False

        inserted = False
        attempts = 0
        while not inserted and attempts < 5:
            jobcard_no = job_card.jobcard_no
            if not jobcard_no:
                jobcard_no = JobCardOperations._generate_unique_jobcard_no()
            elif job_cards_collection.find_one({"jobcard_no": jobcard_no}):
                raise HTTPException(status_code=400, detail="Job Card number already exists")

            jobcard_dict["jobcard_no"] = jobcard_no
            jobcard_dict["jobcard_id"] = utils.generate_custom_id("JBC", job_cards_collection, "jobcard_id")

            try:
                job_cards_collection.insert_one(jobcard_dict)
                inserted = True
            except DuplicateKeyError:
                if job_card.jobcard_no:
                    raise HTTPException(status_code=400, detail="Job Card number already exists")
                jobcard_dict.pop("_id", None)
                attempts += 1
                if attempts >= 5:
                    raise HTTPException(status_code=409, detail="System busy. Failed to generate a unique Job Card number. Please try again.")

        jobcard_dict.pop("_id", None)
        sync_job_card(jobcard_dict)

        if JobCardOperations._get_current_process_step(current_user) == 1:
            part_name = part.get("name", "PRODUCT")
            plant_id = current_user.get("plant_id") or "PLT26AAAA0001"
            qr_ids = utils.generate_dynamic_product_qr_ids(part_name, plant_id, job_card.quantity)
            now = utils.get_current_time()
            qr_records = []
            for qr_id in qr_ids:
                qr_records.append({
                    "qr_id": qr_id,
                    "jobcard_id": jobcard_dict["jobcard_id"],
                    "part_id": part_id,
                    "master_admin_id": current_user["user_id"],
                    "status": "UNUSED",
                    "created_at": now
                })
            if qr_records:
                qr_master_collection.insert_many(qr_records)
                sync_qr_masters_batch(qr_records)
                
            JobCardOperations._perform_auto_scan_for_jobcard(jobcard_dict, qr_ids, current_user)
        
        JobCardOperations._enrich_variant_fields(jobcard_dict)
        return jobcard_dict
    @staticmethod
    def download_sample_xlsx():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Job Card Import Sample"
        
        ws.append(["Product ID"])
        
        ws.append(["PRD26AA00000001"])
        ws.append(["PRD26AA00000002"])
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        headers = {
            'Content-Disposition': 'attachment; filename="job_card_import_sample.xlsx"'
        }
        
        return StreamingResponse(
            buffer, 
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            headers=headers
        )

    @staticmethod
    def generate_reverse_sequence_xlsx(data: schemas.JobCardReverseSequence):
        start_id = data.start_id
        quantity = data.quantity
        
        match = re.search(r'(\d+)$', start_id)
        if match:
            numeric_part = match.group(1)
            prefix = start_id[:match.start()]
            start_num = int(numeric_part)
            padding = len(numeric_part)
        else:
            prefix = start_id
            start_num = 1
            padding = 1
            
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet(title="Generated IDs")
        ws.append(["Product ID"])
        
        for i in range(quantity):
            new_id = f"{prefix}{start_num + i:0{padding}d}"
            ws.append([new_id])
            
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        headers = {
            'Content-Disposition': f'attachment; filename="sequence_{start_id}.xlsx"'
        }
        
        return StreamingResponse(
            buffer, 
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            headers=headers
        )

    @staticmethod
    def print_labels(jobcard_id: str, current_user: dict, start_index: int = 1, limit: int = None, qr_id: str = None):
        plant_id = current_user.get("plant_id")
        process_id = current_user.get("process_id")
        query = {"jobcard_id": jobcard_id}
        if current_user.get("role") != "Super Admin":
            if plant_id and process_id:
                query["$or"] = [
                    {"created_by": current_user["user_id"]},
                    {"plant_id": plant_id, "process_id": process_id}
                ]
            else:
                query["created_by"] = current_user["user_id"]
                
        job_card = job_cards_collection.find_one(query)
        if not job_card:
            raise HTTPException(status_code=404, detail="Job Card not found")
            
        JobCardOperations._enrich_variant_fields(job_card)
        
        qrs = list(qr_master_collection.find({"jobcard_id": jobcard_id}).sort("qr_id", 1))
        if not qrs:
            raise HTTPException(status_code=400, detail="No QR Codes found for this Job Card")
            
        total_count = len(qrs)
        
        if qr_id:
            filtered_qrs = [(idx + 1, q) for idx, q in enumerate(qrs) if q["qr_id"] == qr_id]
            if not filtered_qrs:
                raise HTTPException(status_code=404, detail=f"QR ID {qr_id} not found in this Job Card")
        else:
            offset = max(0, start_index - 1)
            qrs_with_nums = [(idx + 1, q) for idx, q in enumerate(qrs)]
            filtered_qrs = qrs_with_nums[offset:]
            if limit is not None and limit > 0:
                filtered_qrs = filtered_qrs[:limit]
                
        if not filtered_qrs:
            raise HTTPException(status_code=400, detail="No labels selected for printing with current filters")
            
        width_pts = 100 * 2.8346
        height_pts = 85 * 2.8346
        
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=(width_pts, height_pts))
        
        model_name = str(job_card.get("product_model_name") or job_card.get("model_name") or "VEGA").strip()
        submodel_name = str(job_card.get("submodel_name") or job_card.get("part_model") or "VEGA HELMET").strip()
        color = str(job_card.get("color") or "N/A").strip()
        size_val = job_card.get("size")
        size_name = str(job_card.get("size_name") or "").strip()
        if size_val is not None:
            size_display = f"{size_val} ({size_name})" if size_name else str(size_val)
        else:
            size_display = size_name if size_name else "N/A"
        
        sku = str(job_card.get("variant_sku") or job_card.get("jobcard_no") or "N/A").strip()
        jc_currency = job_card.get("currency", "INR")
        sym = utils.get_currency_symbol(jc_currency)

        mrp_raw = job_card.get("mrp")
        mrp_val = None
        if isinstance(mrp_raw, dict):
            mrp_val = mrp_raw.get(jc_currency)
            if mrp_val is None:
                mrp_val = mrp_raw.get("INR")
            if mrp_val is None and mrp_raw:
                mrp_val = next(iter(mrp_raw.values()), None)
        elif isinstance(mrp_raw, (int, float)):
            mrp_val = float(mrp_raw)
        mrp_display = f"{sym} {mrp_val:,.2f}/-" if mrp_val is not None else f"{sym} N/A"
        
        mfg_date = str(job_card.get("jobcard_date") or "").strip()
        if not mfg_date:
            mfg_date = utils.get_current_time().strftime("%d/%m/%Y")
            
        product_name = "VEGA HELMET" if "VEGA" in sku.upper() else "AXOR HELMET"
        gs1_val = str(job_card.get("gs1_barcode") or job_card.get("carton_barcode") or "8901234567890").strip()
        
        batch_no = str(job_card.get("jobcard_no") or "N/A").strip()
        raw_mfg_date = job_card.get("jobcard_date")
        try:
            if raw_mfg_date:
                dt = datetime.strptime(raw_mfg_date, "%Y-%m-%d")
                mfg_month_year = dt.strftime("%B %Y").upper()
            else:
                mfg_month_year = utils.get_current_time().strftime("%B %Y").upper()
        except Exception:
            mfg_month_year = str(raw_mfg_date) if raw_mfg_date else utils.get_current_time().strftime("%B %Y").upper()

        net_weight_val = job_card.get("box_weight")
        net_weight_display = f"{net_weight_val}g" if net_weight_val else "1100g"

        mfg_address_line = job_card.get("plant_address") or ""
        
        mrp_display = f"{sym} {mrp_val:,.0f}/-" if mrp_val is not None else f"{sym} N/A"

        brand_doc = None
        model_id = job_card.get("model_id")
        if model_id:
            model_doc = product_models_collection.find_one({"model_id": model_id})
            if model_doc and model_doc.get("brand_id"):
                brand_doc = product_brands_collection.find_one({"brand_id": model_doc["brand_id"]})

        subcategory_name = None
        category_name = None
        if model_id:
            if not model_doc:
                model_doc = product_models_collection.find_one({"model_id": model_id})
            if model_doc:
                if model_doc.get("subcategory_id"):
                    subcat_doc = product_subcategories_collection.find_one({"subcategory_id": model_doc["subcategory_id"]})
                    if subcat_doc:
                        subcategory_name = subcat_doc.get("name", "").upper()
                if model_doc.get("category_id"):
                    cat_doc = product_categories_collection.find_one({"category_id": model_doc["category_id"]})
                    if cat_doc:
                        category_name = cat_doc.get("name", "").upper()

        for overall_num, qr_rec in filtered_qrs:
            qr_id = qr_rec["qr_id"]
            
            c.setLineWidth(1)
            c.setStrokeColorRGB(0, 0, 0)
            c.roundRect(4, 4, width_pts - 8, height_pts - 8, 4, stroke=1, fill=0)
            
            mid_y = height_pts - 134
            bot_y = 26
            c.line(4, mid_y, width_pts - 4, mid_y)
            c.line(4, bot_y, width_pts - 4, bot_y)
            
            qr_x = 235
            c.line(qr_x, height_pts - 4, qr_x, mid_y)
            c.line(95, mid_y, 95, bot_y)

            def draw_clipped_string(x, y, text, font, size, max_width):
                c.setFont(font, size)
                txt = str(text)
                while c.stringWidth(txt, font, size) > max_width and len(txt) > 1:
                    txt = txt[:-1]
                c.drawString(x, y, txt)
            vega_logo_path = os.path.join(os.path.dirname(__file__), "..", "vega.png")
            top_logo_drawn = False
            
            b_logo_url = brand_doc.get("logo_url") if brand_doc else job_card.get("brand_logo_url")
            if b_logo_url:
                try:
                    if b_logo_url.startswith('http'):
                        req = urllib.request.Request(b_logo_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            img_data = resp.read()
                        b_reader = ImageReader(io.BytesIO(img_data))
                    else:
                        brand_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", b_logo_url.lstrip('/')))
                        b_reader = ImageReader(brand_path)
                        
                    c.drawImage(b_reader, 10, height_pts - 44, width=119.05, height=39.68,
                                preserveAspectRatio=True, mask='auto')
                    top_logo_drawn = True
                except Exception as e:
                    print(f"Brand logo load failed for {b_logo_url}: {e}")
                    
            if not top_logo_drawn and os.path.exists(vega_logo_path):
                c.drawImage(ImageReader(vega_logo_path), 10, height_pts - 44, width=119.05, height=39.68,
                            preserveAspectRatio=True, mask='auto')

            # MANUFACTURED BY block
            mfg_y = height_pts - 56
            c.setFillColorRGB(0, 0, 0)
            c.roundRect(10, mfg_y, 65, 10, 2, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 4.25)
            c.drawString(14, mfg_y + 3, "MANUFACTURED BY:")
            c.setFillColorRGB(0, 0, 0)

            mfg_y -= 10
            c.setFont("Helvetica-Bold", 4.25)
            c.drawString(10, mfg_y, "VEGA AUTO ACCESSORIES LIMITED")

            mfg_y -= 8
            c.setFont("Helvetica", 4.25)
            mfg_lines = [
                mfg_address_line if mfg_address_line else "Plot No. 12-B, Sy. No. 342 (Old 690),",
                "BEMCIEL Industrial Estate,",
                "Udyambag, Belagavi,",
                "Karnataka - 590008, India."
            ]
            for ln in mfg_lines:
                c.drawString(10, mfg_y, ln)
                mfg_y -= 6.5

            # Made in India / Vega branding
            mfg_y -= 14
            
            # 1. Draw Lion Logo (make.png) on the left
            lion_drawn = False
            try:
                make_path = os.path.join(os.path.dirname(__file__), "..", "make.png")
                if os.path.exists(make_path):
                    c.drawImage(ImageReader(make_path), 10, mfg_y - 5, width=32, height=18,
                                preserveAspectRatio=True, mask='auto')
                    lion_drawn = True
            except Exception:
                pass

            if os.path.exists(vega_logo_path):
                try:
                    c.drawImage(ImageReader(vega_logo_path), 46, mfg_y + 1, width=32, height=12,
                                preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass
            
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(45, mfg_y - 6, "MADE IN INDIA")


            c.setFont("Helvetica-Bold", 7.08)
            
            display_subcategory = (subcategory_name or str(job_card.get("helmet_type") or "FULL FACE HELMET")).upper()
            
            c.drawString(128, height_pts - 16, display_subcategory)
            c.setLineWidth(0.5)
            c.line(128, height_pts - 32, qr_x - 4, height_pts - 32)

            details_y = height_pts - 42
            line_ht   = 8.2
            val_x     = 182
            max_val_w = qr_x - val_x - 4
            
            def draw_kv(y_pos, key, val):
                c.setFont("Helvetica-Bold", 5.67)
                c.drawString(128, y_pos, key)
                c.drawString(val_x - 5, y_pos, ":")
                draw_clipped_string(val_x, y_pos, val, "Helvetica", 5.67, max_val_w)

            draw_kv(details_y,                "BRAND",           job_card.get("brand_name") or "VEGA")
            draw_kv(details_y - line_ht,      "MODEL",           model_name.upper())
            draw_kv(details_y - line_ht * 2,  "STYLE",           submodel_name.upper())
            draw_kv(details_y - line_ht * 3,  "SKU",             sku.upper())
            draw_kv(details_y - line_ht * 4,  "NET QUANTITY",    "1 N")
            draw_kv(details_y - line_ht * 5,  "BATCH NO.",       batch_no)
            draw_kv(details_y - line_ht * 6,  "MFG.",            mfg_month_year)
            draw_kv(details_y - line_ht * 7,  "COLOR",           color.upper())
            draw_kv(details_y - line_ht * 8,  "SIZE",            size_display)
            draw_kv(details_y - line_ht * 9,  "NET WEIGHT",      net_weight_display)

            qr_top = height_pts - 20
            qr = qrcode.QRCode(version=1, border=0)
            qr.add_data(qr_id)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_io = io.BytesIO()
            try:
                qr_img.save(qr_io, format="PNG")
            except TypeError:
                # Fallback for PyPNGImage which doesn't accept 'format' keyword argument
                qr_img.save(qr_io)
            qr_io.seek(0)
            
            qr_size = 28.35  # 10x10 MM
            c.drawImage(ImageReader(qr_io), width_pts - qr_size - 8, qr_top - qr_size, width=qr_size, height=qr_size)
            
            c.saveState()
            c.translate(qr_x + 5, qr_top - qr_size)
            c.rotate(90)
            c.setFont("Helvetica-Bold", 3.8)
            # Center it along the QR code's height
            c.drawCentredString(qr_size / 2, 0, "VEGA CENTRAL QR CODE")
            c.restoreState()

            bc_bot = mid_y + 8
            try:
                gs1_digits = "".join(ch for ch in gs1_val if ch.isdigit())
                if len(gs1_digits) >= 12:
                    gs1_for_barcode = gs1_digits[:12]
                else:
                    gs1_for_barcode = gs1_digits.zfill(12)

                EAN = barcode.get_barcode_class('ean13')
                ean = EAN(gs1_for_barcode, writer=ImageWriter())
                ean.default_writer_options['write_text'] = True
                ean.default_writer_options['font_size'] = 14
                ean.default_writer_options['text_distance'] = 2.0
                barcode_io = io.BytesIO()
                ean.write(barcode_io)
                barcode_io.seek(0)
                
                c.saveState()
                c.translate(width_pts - 10, bc_bot - 2)
                c.rotate(90)
                c.drawImage(ImageReader(barcode_io), 0, 0, width=55, height=28.35, preserveAspectRatio=False)
                c.restoreState()

                c.saveState()
                c.translate(width_pts - 38, bc_bot - 2)
                c.rotate(90)
                c.setFont("Helvetica-Bold", 5)
                c.drawCentredString(27.5, 0, "EAN / GTIN-13")
                c.restoreState()
            except Exception as e:
                print(f"Failed to draw barcode: {e}")

            cc_y = mid_y - 12
            c.setFillColorRGB(0, 0, 0)
            c.roundRect(6, cc_y, 84, 9, 2, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 4.25)
            c.drawCentredString(6 + 42, cc_y + 2.5, "CUSTOMER CARE DETAILS")
            c.setFillColorRGB(0, 0, 0)

            cc_y -= 11
            c.setFont("Helvetica-Bold", 4.25)
            c.drawString(6, cc_y, "Consumer care officer")
            
            cc_y -= 8
            c.setFont("Helvetica", 4.25)
            cc_lines = [
                "Plot No. 12-B, Sy. No. 342 (Old 690),",
                "BEMCIEL Industrial Estate,",
                "Udyambag, Belagavi,",
                "Karnataka - 590008, India."
            ]
            for ln in cc_lines:
                c.drawString(6, cc_y, ln)
                cc_y -= 6.8
            def draw_png_icon(filename, x, y, size):
                try:
                    icon_path = os.path.join(os.path.dirname(__file__), "..", filename)
                    if os.path.exists(icon_path):
                        c.drawImage(ImageReader(icon_path), x, y - size/4, width=size, height=size, preserveAspectRatio=True, mask='auto')
                except Exception as e:
                    print(f"Failed to load PNG {filename}: {e}")

            cc_y -= 2
            icon_size = 5
            draw_png_icon("email.png", 6, cc_y, icon_size)
            c.drawString(6 + icon_size + 2, cc_y, "Email: support@vegaauto.in")
            cc_y -= 7
            draw_png_icon("call.png", 6, cc_y, icon_size)
            c.drawString(6 + icon_size + 2, cc_y, "Call: 0831 421 8444")
            cc_y -= 7
            draw_png_icon("web.png", 6, cc_y, icon_size)
            c.drawString(6 + icon_size + 2, cc_y, "www.vegaauto.in")


            product_images = job_card.get("product_images") or []
            if product_images:
                first_img_url = product_images[0]
                img_area_x = 97   
                img_area_w = 70.87   # 25 MM
                img_area_h = 62.36   # 22 MM
                try:
                    if first_img_url.startswith('http'):
                        req = urllib.request.Request(first_img_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            img_data = resp.read()
                        var_reader = ImageReader(io.BytesIO(img_data))
                    else:
                        abs_img = os.path.join(os.path.dirname(__file__), "..", "..", first_img_url.lstrip('/'))
                        var_reader = ImageReader(os.path.normpath(abs_img))
                    c.drawImage(var_reader, img_area_x, bot_y + 4, width=img_area_w, height=img_area_h,
                                preserveAspectRatio=True, mask='auto')
                except Exception as e:
                    print(f"Failed to load variant image ({first_img_url}): {e}")

            # ── Bottom-Right: MRP & Certifications ─────────────────────────
            mrp_box_x = 168
            mrp_box_w = width_pts - mrp_box_x - 6   # fits within label
            mrp_y = mid_y - 34
            c.setLineWidth(0.8)
            c.roundRect(mrp_box_x, mrp_y, mrp_box_w, 26, 4)
            # MRP value – scale font to fit (4mm -> 11.34 pts)
            mrp_str = f"MRP   :   {sym} {mrp_val:,.0f}/-" if mrp_val is not None else f"MRP   :   {sym} N/A"
            mrp_font = 11.34
            while c.stringWidth(mrp_str, "Helvetica-Bold", mrp_font) > mrp_box_w - 6 and mrp_font > 6:
                mrp_font -= 0.5
            c.setFont("Helvetica-Bold", mrp_font)
            c.drawCentredString(mrp_box_x + mrp_box_w / 2, mrp_y + 14, mrp_str)

            c.setFont("Helvetica", 5.5)
            c.drawCentredString(mrp_box_x + mrp_box_w / 2, mrp_y + 4, "(INCLUSIVE OF ALL TAXES)")

            bis_y = mrp_y - 6
            c.setFont("Helvetica", 3.6)
            c.drawString(169, bis_y, "For BIS certification details, please visit: www.bis.gov.in")
            c.drawString(169, bis_y - 4.5, "(Search CM/L number)")

            certs = job_card.get('certification') or []
            valid_certs = []
            for cert in certs:
                cert_upper = cert.upper()
                if cert_upper in ['ISI', 'ECE', 'ONU', 'DOT']:
                    valid_certs.append(cert_upper)

            if valid_certs:
                icon_width = 22
                icon_gap = 10
                total_w = len(valid_certs) * icon_width + (len(valid_certs) - 1) * icon_gap
                cert_x_start = mrp_box_x + (mrp_box_w - total_w) / 2
                cert_y = bot_y + 6
                
                for idx, cert in enumerate(valid_certs):
                    icon_path = None
                    if cert == 'ISI':
                        icon_path = os.path.join(os.path.dirname(__file__), '..', 'isi.png')
                    elif cert in ('ECE', 'ONU'):
                        icon_path = os.path.join(os.path.dirname(__file__), '..', 'ece.png')
                    elif cert == 'DOT':
                        icon_path = os.path.join(os.path.dirname(__file__), '..', 'dot.png')
                    
                    if icon_path and os.path.exists(icon_path):
                        try:
                            img = ImageReader(icon_path)
                            c.drawImage(img, cert_x_start + idx * (icon_width + icon_gap), cert_y, 
                                        width=icon_width, height=icon_width, preserveAspectRatio=True, mask='auto')
                        except Exception as e:
                            print(f"Failed to draw certification icon for {cert}: {e}")

            warn_y = bot_y - 9
            warn_icon_size = 8
            draw_png_icon("warning.png", 8, warn_y - 3, warn_icon_size)
            
            c.setFont("Helvetica-Bold", 4.8)
            c.drawString(18, warn_y, "WARNING: No helmet can protect the wearer against all foreseeable impacts.")
            c.setFont("Helvetica", 4.5)
            c.drawString(18, warn_y - 6, "For maximum protection, the helmet must be of good fit and the chin strap must be securely fastened.")

            book_icon_size = 9
            # width_pts is right edge, so align book icon to the left of the text
            book_x = width_pts - 55
            draw_png_icon("book.png", book_x, warn_y - 3, book_icon_size)
            
            c.setFont("Helvetica-Bold", 4)
            c.drawRightString(width_pts - 10, warn_y, "Read user manual")
            c.drawRightString(width_pts - 10, warn_y - 6, "before use.")

            c.showPage()
            
        c.save()
        pdf_buffer.seek(0)
        
        headers = {
            'Content-Disposition': f'attachment; filename="labels_jobcard_{jobcard_id}.pdf"'
        }
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers=headers
        )

    @staticmethod
    def get_jobcard_qrs_detailed(jobcard_id: str, current_user: dict, page: int = 1, limit: int = 50, search: str = ""):
        from ..database import (
            scanner_processes_collection,
            assembly_processes_collection,
            dispatch_processes_collection,
            qr_master_collection,
            job_cards_collection
        )
        from ..firebase_client import update_rtdb
        
        jobcard = job_cards_collection.find_one({"jobcard_id": jobcard_id})
        if not jobcard:
            raise HTTPException(status_code=404, detail="Job Card not found")
            
        # ── Build base filter (with optional search) ───────────────────────────
        qr_filter: dict = {"jobcard_id": jobcard_id}
        if search and search.strip():
            qr_filter["qr_id"] = {"$regex": search.strip(), "$options": "i"}

        # 1. Paginated QR retrieval
        total_qrs = qr_master_collection.count_documents(qr_filter)
        
        if page < 1:
            page = 1
        if limit < 1:
            limit = 50
            
        skip = (page - 1) * limit
        qrs = list(qr_master_collection.find(qr_filter).sort("qr_id", 1).skip(skip).limit(limit))
        qr_ids = [q["qr_id"] for q in qrs if q.get("qr_id")]
        
        # 2. Self-Healing check: see if any QR in this jobcard has been scanned
        any_scanned = False
        all_qrs_cursor = qr_master_collection.find({"jobcard_id": jobcard_id}, {"qr_id": 1})
        all_qr_ids = [q["qr_id"] for q in all_qrs_cursor if q.get("qr_id")]
        if all_qr_ids:
            first_scan = scanner_processes_collection.find_one({"qr_id": {"$in": all_qr_ids}})
            if first_scan:
                any_scanned = True
                
        jc_status = jobcard.get("status", "CREATED")
        if jc_status == "CREATED" and any_scanned:
            jc_status = "IN PROGRESS"
            job_cards_collection.update_one(
                {"jobcard_id": jobcard_id},
                {"$set": {"status": "IN PROGRESS"}}
            )
            update_rtdb(f"/job_cards/{jobcard_id}", {"status": "IN PROGRESS"})
            
        # 3. High-Performance Bulk Queries for paginated QRs
        all_scans = list(scanner_processes_collection.find({"qr_id": {"$in": qr_ids}})) if qr_ids else []
        all_assemblies = list(assembly_processes_collection.find({
            "$or": [{"component_ids": {"$in": qr_ids}}, {"qr_ids": {"$in": qr_ids}}]
        })) if qr_ids else []
        all_dispatches = list(dispatch_processes_collection.find({
            "$or": [{"qr_ids": {"$in": qr_ids}}, {"component_ids": {"$in": qr_ids}}]
        })) if qr_ids else []
        
        # Build In-Memory Grouping Maps
        scans_by_qr = {}
        for s in all_scans:
            qid = s.get("qr_id")
            if qid:
                scans_by_qr.setdefault(qid, []).append(s)
                 
        assemblies_by_qr = {}
        for a in all_assemblies:
            qids = set()
            if a.get("component_ids"):
                for item in a["component_ids"]:
                    if isinstance(item, list):
                        qids.update(item)
                    else:
                        qids.add(item)
            if a.get("qr_ids"):
                for item in a["qr_ids"]:
                    if isinstance(item, list):
                        qids.update(item)
                    else:
                        qids.add(item)
            for qid in qids:
                assemblies_by_qr.setdefault(qid, []).append(a)
                 
        dispatches_by_qr = {}
        for d in all_dispatches:
            qids = set()
            if d.get("qr_ids"):
                for item in d["qr_ids"]:
                    if isinstance(item, list):
                        qids.update(item)
                    else:
                        qids.add(item)
            if d.get("component_ids"):
                for item in d["component_ids"]:
                    if isinstance(item, list):
                        qids.update(item)
                    else:
                        qids.add(item)
            for qid in qids:
                dispatches_by_qr.setdefault(qid, []).append(d)
                 
        # Process each QR
        qrs_detailed = []
        for q in qrs:
            qr_id = q["qr_id"]
            
            qr_scans = scans_by_qr.get(qr_id, [])
            qr_asms = assemblies_by_qr.get(qr_id, [])
            qr_dsps = dispatches_by_qr.get(qr_id, [])
            
            history = []
            for s in qr_scans:
                s_copy = dict(s)
                s_copy.pop("_id", None)
                s_copy["type"] = "Reader Process"
                history.append(s_copy)
                
            for a in qr_asms:
                a_copy = dict(a)
                a_copy.pop("_id", None)
                a_copy["type"] = "Assembly Process"
                history.append(a_copy)
                
            for d in qr_dsps:
                d_copy = dict(d)
                d_copy.pop("_id", None)
                d_copy["type"] = "Dispatch Process"
                history.append(d_copy)
                
            # Chronological sort
            history.sort(key=lambda x: x["start_time"] if x.get("start_time") else datetime.min)
            
            # Quality status from latest event
            quality_status = "NOT SCANNED"
            if history:
                latest_event = history[-1]
                quality_status = latest_event.get("inspection_status", "NOT SCANNED")

            # Derive real-time status from history
            db_status = q.get("status", "UNUSED")
            if history:
                effective_status = "IN USE"
            elif db_status == "SCRAPPED":
                effective_status = "SCRAPPED"
            else:
                effective_status = db_status

            qrs_detailed.append({
                "qr_id": qr_id,
                "status": effective_status,
                "quality_status": quality_status,
                "created_at": q.get("created_at"),
                "history": history
            })
            
        return {
            "jobcard_id": jobcard_id,
            "jobcard_no": jobcard.get("jobcard_no"),
            "part_id": jobcard.get("part_id"),
            "part_model": jobcard.get("part_model"),
            "quantity": jobcard.get("quantity"),
            "status": jc_status,
            "total_qrs": total_qrs,
            "page": page,
            "limit": limit,
            "total_pages": (total_qrs + limit - 1) // limit if limit > 0 else 1,
            "qrs": qrs_detailed
        }

    @staticmethod
    def delete_qrs(qr_ids: list[str], current_user: dict):
        from ..database import (
            qr_master_collection,
            scanner_processes_collection,
            assembly_processes_collection,
            dispatch_processes_collection,
            job_cards_collection
        )
        
        qrs = list(qr_master_collection.find({"qr_id": {"$in": qr_ids}}))
        if not qrs:
            raise HTTPException(status_code=404, detail="No matching QR codes found")
            
        found_ids = [q["qr_id"] for q in qrs]
        
        scanned_qrs = set()
        
        # Check scanner processes
        scans = list(scanner_processes_collection.find({"qr_id": {"$in": found_ids}}))
        for s in scans:
            scanned_qrs.add(s["qr_id"])
            
        # Check assemblies
        assemblies = list(assembly_processes_collection.find({
            "$or": [{"component_ids": {"$in": found_ids}}, {"qr_ids": {"$in": found_ids}}]
        }))
        for a in assemblies:
            for q in a.get("component_ids", []):
                scanned_qrs.add(q)
            for q in a.get("qr_ids", []):
                scanned_qrs.add(q)
                
        # Check dispatches
        dispatches = list(dispatch_processes_collection.find({
            "$or": [{"qr_ids": {"$in": found_ids}}, {"component_ids": {"$in": found_ids}}]
        }))
        for d in dispatches:
            for q in d.get("qr_ids", []):
                scanned_qrs.add(q)
            for q in d.get("component_ids", []):
                scanned_qrs.add(q)
                
        # Check status in qr_master
        for q in qrs:
            if q.get("status") == "IN USE":
                scanned_qrs.add(q["qr_id"])
                
        to_delete = [qid for qid in found_ids if qid not in scanned_qrs]
        blocked = [qid for qid in found_ids if qid in scanned_qrs]
        
        if not to_delete:
            raise HTTPException(
                status_code=400, 
                detail=f"None of the QR codes could be deleted. Blocked QRs (scanned or in-use): {blocked}"
            )
            
        # Delete safe QR records
        qr_master_collection.delete_many({"qr_id": {"$in": to_delete}})
        
        # Decrement parent Job Card quantity
        jobcard_adjustments = {}
        for q in qrs:
            if q["qr_id"] in to_delete and q.get("jobcard_id"):
                jobcard_adjustments[q["jobcard_id"]] = jobcard_adjustments.get(q["jobcard_id"], 0) + 1
                
        for jc_id, dec in jobcard_adjustments.items():
            job_cards_collection.update_one(
                {"jobcard_id": jc_id},
                {"$inc": {"quantity": -dec}}
            )
            
        return {
            "detail": f"Successfully deleted {len(to_delete)} QR code(s).",
            "deleted_qrs": to_delete,
            "blocked_qrs": blocked
        }

# Duplicate JobCardAssembleCreate removed (definition now resides in schemas)
@router.post(
    "/assemble",
    response_model=schemas.JobCard,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Job Card based on a product variant (assemble)",
    description="Creates a job card and generates QR codes using the provided variant SKU. The request body must contain the standard JobCardCreate fields plus a `variant_sku` field."
)
def create_assemble_job_card(
    assemble_req: schemas.JobCardAssembleCreate,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"])),
):
    return JobCardOperations.create_assemble_job_card(
        assemble_req.job_card, assemble_req.variant_sku, current_user
    )

@router.post("/", response_model=schemas.JobCard, status_code=status.HTTP_201_CREATED)
def create_job_card(
    job_card: schemas.JobCardCreate, 
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.create_job_card(job_card, current_user)

@router.get("/", response_model=schemas.JobCardResponse)
def get_job_cards(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin"]))
):
    return JobCardOperations.get_job_cards(current_user, page=page, limit=limit, search=search)

@router.delete("/{jobcard_id}")
def delete_job_card(
    jobcard_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.delete_job_card(jobcard_id, current_user)

@router.get("/{jobcard_id}/download-qrs")
def download_jobcard_qrs(
    jobcard_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.download_qrs(jobcard_id, current_user)

@router.get("/{jobcard_id}/print-labels")
def print_jobcard_labels(
    jobcard_id: str,
    start_index: int = 1,
    limit: int = None,
    qr_id: str = None,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.print_labels(
        jobcard_id=jobcard_id,
        current_user=current_user,
        start_index=start_index,
        limit=limit,
        qr_id=qr_id
    )

@router.get("/{jobcard_id}", response_model=schemas.JobCard)
def get_job_card(
    jobcard_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin"]))
):
    return JobCardOperations.get_job_card(jobcard_id, current_user)

@router.get("/{jobcard_id}/qrs-detailed")
def get_jobcard_qrs_detailed(
    jobcard_id: str,
    page: int = 1,
    limit: int = 50,
    search: str = "",
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin"]))
):
    return JobCardOperations.get_jobcard_qrs_detailed(
        jobcard_id, current_user, page=page, limit=limit, search=search
    )

@router.put("/{jobcard_id}")
def update_job_card_status(
    jobcard_id: str,
    status_update: schemas.JobCardStatusUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.update_job_card_status(jobcard_id, status_update, current_user)

@router.post("/reverse-import/preview", response_model=list[schemas.JobCardImportPreview])
def preview_reverse_import(
    file: UploadFile = File(...),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.preview_reverse_import(file, current_user)

@router.post("/reverse-import/confirm", response_model=schemas.JobCard)
def confirm_reverse_import(
    data: schemas.JobCardReverseCreate,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.create_reverse_job_card(data, current_user)

@router.get("/reverse-import/sample")
def download_sample_xlsx(
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.download_sample_xlsx()

@router.post("/reverse-import/generate-sequence")
def generate_reverse_sequence_xlsx(
    data: schemas.JobCardReverseSequence,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return JobCardOperations.generate_reverse_sequence_xlsx(data)

@router.delete("/qrs/{qr_id}")
def delete_single_qr(
    qr_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin"]))
):
    return JobCardOperations.delete_qrs([qr_id], current_user)

@router.post("/qrs/bulk-delete")
def bulk_delete_qrs(
    data: schemas.QRBulkDelete,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin"]))
):
    return JobCardOperations.delete_qrs(data.qr_ids, current_user)
