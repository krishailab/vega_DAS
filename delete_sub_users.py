import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import users_collection

print("Deleting all sub-users created by the script...")

# Delete sub-users identified by the specific last_name and sub roles
result = users_collection.delete_many({
    "last_name": "SubUser",
    "role": {"$in": ["Scanner", "Linker", "Inspector"]}
})

print(f"Successfully deleted {result.deleted_count} sub-users.")
