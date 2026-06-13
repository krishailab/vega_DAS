import os
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import time

# Load dotenv to get config
load_dotenv()

import app.firebase_client as fc

fc.init_firebase()

if not fc._firebase_initialized or fc._db is None:
    print("Error: Firebase Admin SDK failed to initialize. Make sure FIREBASE_SERVICE_ACCOUNT and FIREBASE_DATABASE_URL are correct in your .env file.")
    exit(1)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
db = client["vega_track"]

def sync_collection_to_firebase(collection_name, firebase_path, id_field, batch_size=200):
    print(f"\n--- Syncing '{collection_name}' collection to Firebase path '{firebase_path}' ---")
    collection = db[collection_name]
    
    cursor = collection.find({})
    records = list(cursor)
    total = len(records)
    print(f"Found {total} records in MongoDB.")
    
    if total == 0:
        print("No records to sync.")
        return
        
    ref = fc._db.reference(firebase_path)
    
    # Process in batches to prevent payload limits and optimize network speed
    for i in range(0, total, batch_size):
        batch = records[i:i+batch_size]
        updates = {}
        
        for doc in batch:
            doc_id = doc.get(id_field)
            if doc_id:
                # Remove MongoDB _id field and serialize cleanly
                clean = {k: v for k, v in doc.items() if k != "_id"}
                serialized = fc._serialize_for_firebase(clean)
                updates[str(doc_id)] = serialized
                
        if updates:
            try:
                ref.update(updates)
                print(f"Synced {min(i + batch_size, total)}/{total} records...")
            except Exception as e:
                print(f"Error syncing batch at index {i}: {e}")
                time.sleep(1) # Backoff and retry
                try:
                    ref.update(updates)
                except Exception as e2:
                    print(f"Failed to retry batch sync: {e2}")

    print(f"Successfully completed syncing '{collection_name}' to Firebase path '{firebase_path}'!")

def run_full_sync():
    print("Starting full database synchronization to Firebase Realtime Database...")
    
    # 1. Sync QR Master
    sync_collection_to_firebase("qr_master", "/qr_master", "qr_id")
    
    # 2. Sync Products
    sync_collection_to_firebase("products", "/products", "qr_id")
    
    # 3. Sync Scanner Processes
    sync_collection_to_firebase("scanner_processes", "/scanner_processes", "scan_id")
    
    # 4. Sync Assembly Processes
    sync_collection_to_firebase("assembly_processes", "/assembly_processes", "assembly_id")
    
    # 5. Sync Dispatch Processes
    sync_collection_to_firebase("dispatch_processes", "/dispatch_processes", "dispatch_id")
    
    # 6. Sync Job Cards
    sync_collection_to_firebase("job_cards", "/job_cards", "jobcard_id")

    print("\n🎉 Full Firebase RTDB Synchronization completed successfully!")

if __name__ == "__main__":
    run_full_sync()
