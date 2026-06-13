import sys
import os

# Add the project root to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import parts_collection, users_collection

def update_dispatch_assemble():
    true_part_ids = ["PTR26AAAA0008", "PTR26AAAA0009", "PTR26AAAA0010"]
    
    print("Updating Parts...")
    # Update parts to True
    result_true = parts_collection.update_many(
        {"part_id": {"$in": true_part_ids}},
        {"$set": {"is_dispatch_assemble": True}}
    )
    print(f"Parts updated to True: {result_true.modified_count}")
    
    # Update other parts to False
    result_false = parts_collection.update_many(
        {"part_id": {"$nin": true_part_ids}},
        {"$set": {"is_dispatch_assemble": False}}
    )
    print(f"Parts updated to False: {result_false.modified_count}")
    
    print("\nUpdating Master Admins...")
    # Update Master Admins associated with True parts
    admin_result_true = users_collection.update_many(
        {"role": "Master Admin", "part_id": {"$in": true_part_ids}},
        {"$set": {"is_dispatch_assemble": True}}
    )
    print(f"Master Admins updated to True: {admin_result_true.modified_count}")
    
    # Update Master Admins associated with False parts
    admin_result_false = users_collection.update_many(
        {"role": "Master Admin", "part_id": {"$nin": true_part_ids}},
        {"$set": {"is_dispatch_assemble": False}}
    )
    print(f"Master Admins updated to False: {admin_result_false.modified_count}")
    
    print("\nUpdate completed successfully.")

if __name__ == "__main__":
    update_dispatch_assemble()
