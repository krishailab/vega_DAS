import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import users_collection, asset_assignments_collection

print("Starting migration to rename role 'Scanner' to 'Reader' in database...")

# 1. Update users_collection
users_updated = users_collection.update_many(
    {"role": "Scanner"},
    {"$set": {"role": "Reader"}}
)
print(f"Updated {users_updated.modified_count} user(s) in users_collection.")

# 2. Update asset_assignments_collection
assignments_updated = asset_assignments_collection.update_many(
    {"role": "Scanner"},
    {"$set": {"role": "Reader"}}
)
print(f"Updated {assignments_updated.modified_count} assignment record(s) in asset_assignments_collection.")

print("\nRole migration completed successfully!")
