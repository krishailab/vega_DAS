import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import parts_collection, users_collection

print("Starting migration to replace 'is_dispatch_assemble' with 'is_assemble' and 'is_dispatch_admin'...")

# 1. Migrate parts_collection
parts_updated = 0
for part in parts_collection.find({}):
    # Fetch existing or default to False
    val = part.get("is_dispatch_assemble", False)
    
    # Update document with new fields and unset the old field
    parts_collection.update_one(
        {"_id": part["_id"]},
        {
            "$set": {
                "is_assemble": val,
                "is_dispatch_admin": val
            },
            "$unset": {
                "is_dispatch_assemble": ""
            }
        }
    )
    parts_updated += 1

print(f"Migrated {parts_updated} documents in parts_collection.")

# 2. Migrate users_collection
users_updated = 0
for user in users_collection.find({}):
    # Fetch existing or default to False
    val = user.get("is_dispatch_assemble", False)
    
    # Update document with new fields and unset the old field
    users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "is_assemble": val,
                "is_dispatch_admin": val
            },
            "$unset": {
                "is_dispatch_assemble": ""
            }
        }
    )
    users_updated += 1

print(f"Migrated {users_updated} documents in users_collection.")
print("\nMigration completed successfully!")
