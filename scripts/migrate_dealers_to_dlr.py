#!/usr/bin/env python3
import os
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from app.utils import generate_custom_id

load_dotenv()

def migrate_dealers():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    
    users_col = db["users"]
    b2b_orders_col = db["b2b_orders"]
    b2b_cart_col = db["b2b_cart"]
    coin_wallets_col = db["coin_wallets"]
    coin_transactions_col = db["coin_transactions"]

    dealers = list(users_col.find({"role": "Dealer", "user_id": {"$regex": "^EMP"}}))
    print(f"Found {len(dealers)} dealers with old 'EMP' prefix.")

    for dealer in dealers:
        old_id = dealer["user_id"]
        # Generate new ID starting with DLR
        new_id = generate_custom_id("DLR", users_col, "user_id")
        print(f"Migrating Dealer: {old_id} -> {new_id}")

        # 1. Update user document
        users_col.update_one(
            {"_id": dealer["_id"]},
            {"$set": {
                "user_id": new_id,
                "employee_id": new_id
            }}
        )

        # 2. Update b2b orders
        ord_res = b2b_orders_col.update_many({"user_id": old_id}, {"$set": {"user_id": new_id}})
        print(f"  -> Updated {ord_res.modified_count} B2B orders")

        # 3. Update b2b cart
        cart_res = b2b_cart_col.update_many({"user_id": old_id}, {"$set": {"user_id": new_id}})
        print(f"  -> Updated {cart_res.modified_count} B2B cart items")

        # 4. Update coin wallets
        wallet_res = coin_wallets_col.update_many({"user_id": old_id}, {"$set": {"user_id": new_id}})
        print(f"  -> Updated {wallet_res.modified_count} wallets")

        # 5. Update coin transactions
        tx_res = coin_transactions_col.update_many({"user_id": old_id}, {"$set": {"user_id": new_id}})
        print(f"  -> Updated {tx_res.modified_count} coin transactions")

    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate_dealers()
