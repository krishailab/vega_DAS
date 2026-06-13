from app.database import b2b_orders_collection, b2b_invoices_collection

def migrate_orders_invoices():
    print("Starting migration: moving embedded invoices to separate collection...")
    
    # Find orders that have an 'invoices' field that is a list
    orders_with_invoices = list(b2b_orders_collection.find({"invoices": {"$exists": True, "$ne": []}}))
    
    print(f"Found {len(orders_with_invoices)} orders with embedded invoices.")
    
    invoices_migrated = 0
    orders_updated = 0
    
    for order in orders_with_invoices:
        order_id = order.get("order_id")
        invoices = order.get("invoices", [])
        
        if not order_id or not invoices:
            continue
            
        print(f"Processing order {order_id} with {len(invoices)} invoices...")
        
        for inv in invoices:
            # Add order_id reference
            inv["order_id"] = order_id
            
            # Upsert into b2b_invoices collection
            b2b_invoices_collection.update_one(
                {"invoice_id": inv["invoice_id"]},
                {"$set": inv},
                upsert=True
            )
            invoices_migrated += 1
            
        # Remove invoices array from the order document
        b2b_orders_collection.update_one(
            {"order_id": order_id},
            {"$unset": {"invoices": ""}}
        )
        orders_updated += 1
        
    print("Migration summary:")
    print(f"- {invoices_migrated} invoices upserted into b2b_invoices.")
    print(f"- {orders_updated} orders flattened (invoices unset).")
    print("Migration complete!")

if __name__ == "__main__":
    migrate_orders_invoices()
