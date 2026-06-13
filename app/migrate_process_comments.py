import os
import pymongo
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

stations_col = db["stations"]
scanner_processes_col = db["scanner_processes"]
assembly_processes_col = db["assembly_processes"]
dispatch_processes_col = db["dispatch_processes"]

print("Starting migration of existing scans, links, and dispatches to add station_comment...")

# 1. Build a map of station_id -> comment
station_comments = {}
stations_cursor = stations_col.find({}, {"station_id": 1, "comment": 1})
for s in stations_cursor:
    sid = s.get("station_id")
    comment = s.get("comment")
    if sid:
        station_comments[sid] = comment

print(f"Loaded {len(station_comments)} stations with comments.")

# 2. Migrate scanner_processes
scans_updated = 0
scans_cursor = scanner_processes_col.find({"station_comment": {"$exists": False}})
for scan in scans_cursor:
    scan_id = scan.get("scan_id")
    sid = scan.get("station_id")
    if sid in station_comments:
        comment = station_comments[sid]
        scanner_processes_col.update_one(
            {"scan_id": scan_id},
            {"$set": {"station_comment": comment}}
        )
        scans_updated += 1

print(f"Updated {scans_updated} scan processes with station comments.")

# 3. Migrate assembly_processes
links_updated = 0
links_cursor = assembly_processes_col.find({"station_comment": {"$exists": False}})
for link in links_cursor:
    asm_id = link.get("assembly_id")
    sid = link.get("station_id")
    if sid in station_comments:
        comment = station_comments[sid]
        assembly_processes_col.update_one(
            {"assembly_id": asm_id},
            {"$set": {"station_comment": comment}}
        )
        links_updated += 1

print(f"Updated {links_updated} assembly processes with station comments.")

# 4. Migrate dispatch_processes
dispatches_updated = 0
dispatches_cursor = dispatch_processes_col.find({"station_comment": {"$exists": False}})
for dsp in dispatches_cursor:
    dsp_id = dsp.get("dispatch_id")
    sid = dsp.get("station_id")
    if sid in station_comments:
        comment = station_comments[sid]
        dispatch_processes_col.update_one(
            {"dispatch_id": dsp_id},
            {"$set": {"station_comment": comment}}
        )
        dispatches_updated += 1

print(f"Updated {dispatches_updated} dispatch processes with station comments.")
print("\nMigration complete!")
