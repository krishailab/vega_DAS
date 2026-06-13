from app.database import stations_collection, scanner_processes_collection, qr_master_collection
import time

st_id = "STN_TEST_COMMENT"
stations_collection.delete_many({"station_id": st_id})
scanner_processes_collection.delete_many({"qr_id": "QR_TEST_COMMENT"})
qr_master_collection.delete_many({"qr_id": "QR_TEST_COMMENT"})

stations_collection.insert_one({
    "station_id": st_id,
    "name": "Test Station Comment",
    "comment": "THIS IS MY AWESOME COMMENT",
    "process": "TEST_PROCESS",
    "active": True
})

qr_master_collection.insert_one({
    "qr_id": "QR_TEST_COMMENT",
    "part_id": "PART_TEST",
    "created_at": time.time()
})

scanner_processes_collection.insert_one({
    "qr_id": "QR_TEST_COMMENT",
    "scan_id": "SCN_TEST_COMMENT",
    "station_id": st_id,
    "process_name": "TEST_PROCESS",
    "scanner_name": "Tester",
    "start_time": time.time()
})

print("Inserted test data")
