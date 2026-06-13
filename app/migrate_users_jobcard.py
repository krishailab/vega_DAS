import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import users_collection

def migrate_users():
    print("Starting migration to add 'jobcard': True for existing users...")
    
    # Update all users where 'jobcard' field does not exist
    result = users_collection.update_many(
        {"jobcard": {"$exists": False}},
        {"$set": {"jobcard": True}}
    )
    
    print(f"Migration completed!")
    print(f"Matched users: {result.matched_count}")
    print(f"Modified users: {result.modified_count}")

if __name__ == "__main__":
    migrate_users()
