import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

def migrate_users_department():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    users_col = db["users"]
    
    # Fetch all users
    users = list(users_col.find({}))
    print(f"Found {len(users)} users in database.")
    
    updated_count = 0
    for user in users:
        dept = "PRODUCTION"
        res = users_col.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"department": dept}}
        )
        if res.modified_count > 0 or user.get("department") != dept:
            updated_count += 1
            
    print(f"Successfully migrated {updated_count} users to include 'department' = 'PRODUCTION'!")

if __name__ == "__main__":
    migrate_users_department()
