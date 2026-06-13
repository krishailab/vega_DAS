import os
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv

load_dotenv()

def check_admins():
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    users_col = db["users"]
    
    print("Seeded Super Admins in DB:")
    for user in users_col.find({"role": "Super Admin"}):
        print(f"- Email: {user.get('email')}, Dept: {user.get('department')}, Name: {user.get('first_name')} {user.get('last_name')}, ID: {user.get('user_id')}")

if __name__ == "__main__":
    check_admins()
