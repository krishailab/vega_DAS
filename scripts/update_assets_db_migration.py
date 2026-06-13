import sys
import os

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import assets_collection

def update_existing_assets():
    print("Updating existing assets in DB...")
    
    # Update documents where color doesn't exist
    result = assets_collection.update_many(
        {"color": {"$exists": False}},
        {"$set": {"color": None, "guarantee_date": None, "expire_date": None}}
    )
    
    print(f"Matched {result.matched_count} documents and modified {result.modified_count} documents.")
    print("Done!")

if __name__ == "__main__":
    update_existing_assets()
