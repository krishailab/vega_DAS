import sys
import os

# Add the workspace root to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, users_collection, b2b_orders_collection

def migrate():
    print("Starting address migration...")

    # 1. Migrate Users
    users = list(users_collection.find())
    print(f"Found {len(users)} users to process.")
    
    user_map = {} # Keep map of user_id -> name for order migration
    
    for user in users:
        user_id = user.get("user_id")
        first_name = user.get("first_name") or ""
        last_name = user.get("last_name") or ""
        business_name = user.get("business_name") or ""
        
        contact_name = f"{first_name} {last_name}".strip()
        if not contact_name:
            contact_name = business_name
        if not contact_name:
            contact_name = "Dealer User"
            
        user_map[user_id] = contact_name
        
        updated = False
        company_address = user.get("company_address")
        company_addresses = user.get("company_addresses") or []
        
        # Check company_address
        if isinstance(company_address, dict):
            if "name" not in company_address or not company_address["name"]:
                company_address["name"] = contact_name
                updated = True
                
        # Check company_addresses list
        new_addresses = []
        for addr in company_addresses:
            if isinstance(addr, dict):
                if "name" not in addr or not addr["name"]:
                    addr["name"] = contact_name
                    updated = True
                new_addresses.append(addr)
            else:
                new_addresses.append(addr)
                
        if updated:
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "company_address": company_address,
                    "company_addresses": new_addresses
                }}
            )
            print(f"Updated addresses for user {user_id} ({contact_name})")

    # 2. Migrate Orders
    orders = list(b2b_orders_collection.find())
    print(f"Found {len(orders)} B2B orders to process.")
    for order in orders:
        user_id = order.get("user_id")
        contact_name = user_map.get(user_id)
        if not contact_name:
            # Try to get from users collection directly if not loaded
            if user_id:
                u = users_collection.find_one({"user_id": user_id})
                if u:
                    contact_name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("business_name", "")
            if not contact_name:
                contact_name = "Dealer User"
                
        updated = False
        billing_address = order.get("billing_address")
        shipping_address = order.get("shipping_address")
        company_address = order.get("company_address")
        
        set_dict = {}
        if isinstance(billing_address, dict):
            if "name" not in billing_address or not billing_address["name"]:
                billing_address["name"] = contact_name
                set_dict["billing_address"] = billing_address
                updated = True
        if isinstance(shipping_address, dict):
            if "name" not in shipping_address or not shipping_address["name"]:
                shipping_address["name"] = contact_name
                set_dict["shipping_address"] = shipping_address
                updated = True
        if isinstance(company_address, dict):
            if "name" not in company_address or not company_address["name"]:
                company_address["name"] = contact_name
                set_dict["company_address"] = company_address
                updated = True
                
        if updated:
            b2b_orders_collection.update_one(
                {"_id": order["_id"]},
                {"$set": set_dict}
            )
            print(f"Updated addresses for order {order.get('order_id')}")

    print("Migration finished successfully!")

if __name__ == "__main__":
    migrate()
