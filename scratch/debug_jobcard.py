from app.database import job_cards_collection, qr_master_collection, products_collection, assembly_processes_collection, scanner_processes_collection, dispatch_processes_collection, stations_collection, parts_collection
import json

jcid = "JBC26AA0011"
qr_cursor = qr_master_collection.find({"jobcard_id": jcid})
qr_ids = [q["qr_id"] for q in qr_cursor]

for qid in qr_ids:
    print(f"\n--- {qid} ---")
    p = products_collection.find_one({"qr_id": qid})
    print(f"Product overall_status: {p.get('overall_status') if p else 'NOT FOUND'}")
    
    asms = list(assembly_processes_collection.find({"component_ids": qid}).sort("start_time", -1))
    for a in asms:
        station = stations_collection.find_one({"station_id": a.get("station_id")})
        part_name = "Unknown"
        if station and station.get("part_id"):
            part = parts_collection.find_one({"part_id": station.get("part_id")})
            if part: part_name = part.get("name")
        print(f"Assembly: {a.get('process_name')} (Part: {part_name}) at {a.get('start_time')}")

    dsps = list(dispatch_processes_collection.find({"qr_ids": qid}).sort("start_time", -1))
    for d in dsps:
        print(f"Dispatch: {d.get('process_name')} at {d.get('start_time')}")
