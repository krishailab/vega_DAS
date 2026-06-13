import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def update_stations_is_dispatch():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    stations_col = db["stations"]
    
    print("Updating stations...")
    # Update all stations where is_dispatch is missing, setting it to False
    result = stations_col.update_many(
        {"is_dispatch": {"$exists": False}},
        {"$set": {"is_dispatch": False}}
    )
    
    print(f"✅ Matched {result.matched_count} stations.")
    print(f"✅ Modified {result.modified_count} stations.")
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    update_stations_is_dispatch()
