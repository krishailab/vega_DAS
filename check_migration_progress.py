import os
import sys

# Add project root to python path to resolve app imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import job_cards_collection

def check():
    total = job_cards_collection.count_documents({})
    populated = job_cards_collection.count_documents({"completion_percentage": {"$ne": None}})
    completed = job_cards_collection.count_documents({"status": "COMPLETED"})
    print(f"Total Job Cards: {total}")
    print(f"Populated Job Cards: {populated}")
    print(f"Completed Job Cards: {completed}")

if __name__ == "__main__":
    check()
