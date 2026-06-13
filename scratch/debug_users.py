import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import users_collection
for u in users_collection.find({"role": "Master Admin"}):
    print(f"ID: {u.get('user_id')}, Email: {u.get('email')}, Name: {u.get('first_name')} {u.get('last_name')}")
