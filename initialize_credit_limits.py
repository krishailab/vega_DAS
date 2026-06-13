import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import users_collection

def run_migration(default_order_limit, default_overall_limit, overwrite=False):
    print("========== INITIALIZING DEALER CREDIT LIMITS ==========")
    print(f"Target defaults - Order Credit Limit: {default_order_limit}, Overall Credit Limit: {default_overall_limit}")
    print(f"Overwrite existing: {overwrite}")
    
    query = {"role": "Dealer"}
    dealers = list(users_collection.find(query))
    print(f"Found {len(dealers)} dealers in the database.")
    
    updated_count = 0
    for dealer in dealers:
        update_doc = {}
        
        # Check order_credit_limit
        if "order_credit_limit" not in dealer or overwrite:
            update_doc["order_credit_limit"] = default_order_limit
            
        # Check overall_credit_limit
        if "overall_credit_limit" not in dealer or overwrite:
            update_doc["overall_credit_limit"] = default_overall_limit
            
        if update_doc:
            users_collection.update_one(
                {"_id": dealer["_id"]},
                {"$set": update_doc}
            )
            updated_count += 1
            print(f"Updated Dealer {dealer.get('first_name', '')} {dealer.get('last_name', '')} (ID: {dealer.get('user_id')}) -> {update_doc}")
            
    print(f"Successfully initialized limits for {updated_count} dealer(s).")
    print("======================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize B2B Dealer credit limits in users collection.")
    parser.add_argument("--order-limit", type=float, default=10000.0, help="Default single order credit limit (default: 10000.0)")
    parser.add_argument("--overall-limit", type=float, default=20000.0, help="Default overall credit limit (default: 20000.0)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing limits even if they are already set")
    
    args = parser.parse_args()
    run_migration(args.order_limit, args.overall_limit, args.overwrite)
