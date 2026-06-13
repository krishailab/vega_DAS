import os
import sys

# Add project root to python path to resolve app imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import job_cards_collection
from app.api.scan_api import _check_and_update_job_card_completion_sync

def migrate():
    cards = list(job_cards_collection.find({}))
    total = len(cards)
    print(f"Found {total} job cards to migrate.")
    
    updated_count = 0
    for idx, card in enumerate(cards, 1):
        jobcard_id = card.get("jobcard_id")
        if not jobcard_id:
            continue
            
        print(f"[{idx}/{total}] Syncing and updating Job Card: {jobcard_id}...")
        try:
            _check_and_update_job_card_completion_sync(jobcard_id)
            updated_count += 1
        except Exception as e:
            print(f"Error processing {jobcard_id}: {e}")
            
    print(f"Completed! Successfully synchronized {updated_count}/{total} job cards.")

if __name__ == "__main__":
    migrate()
