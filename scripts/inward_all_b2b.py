import sys
import os
import random
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import product_variants_collection, b2b_inward_products_collection
from app import utils

def run():
    print("Fetching all variants from the database...")
    variants = list(product_variants_collection.find({"is_active": True}))
    
    print("Clearing existing B2B inwarded products to re-inward with flags...")
    b2b_inward_products_collection.delete_many({})

    print(f"Found {len(variants)} total active variants.")
    
    new_inwards = []
    
    for variant in variants:
        variant_id = variant.get("variant_id")
            
        # Resolve MRP and Currency
        mrp_raw = variant.get("mrp")
        mrp_val = 0.0
        currency = "CAD"
        if isinstance(mrp_raw, dict):
            if mrp_raw:
                currency = next(iter(mrp_raw.keys()), "CAD")
                mrp_val = mrp_raw.get(currency, 0.0)
        elif isinstance(mrp_raw, (int, float)):
            mrp_val = float(mrp_raw)

        # Dealer price is MRP with the 10% markup removed
        dealer_price = round(mrp_val / 1.10, 2) if mrp_val else 0.0
        
        # Randomize flags (ensure at least one of is_individual or is_carton is True)
        is_individual = random.choice([True, False])
        is_carton = random.choice([True, False])
        if not is_individual and not is_carton:
            is_individual = True
            
        is_featured = random.choice([True, False])
        is_new_arrival = random.choice([True, False])
        is_best_seller = random.choice([True, False])
        
        now = utils.get_current_time()
        
        inward_doc = {
            "variant_id": variant_id,
            "sku_no": variant.get("sku_no"),
            "dealer_price": dealer_price,
            "currency": currency,
            "is_individual": is_individual,
            "is_carton": is_carton,
            "is_featured": is_featured,
            "is_new_arrival": is_new_arrival,
            "is_best_seller": is_best_seller,
            "is_active": True,
            "created_by": "SYSTEM",
            "created_at": now,
            "updated_at": now
        }
        
        new_inwards.append(inward_doc)
        
    if not new_inwards:
        print("No new variants to inward. All variants are already inwarded.")
        return
        
    print(f"Generating IDs and inserting {len(new_inwards)} new B2B products...")
    
    # Generate sequential IDs
    # Since generate_custom_id hits DB per call, doing it in loop can be slow, but it's safe.
    for doc in new_inwards:
        doc["inward_id"] = utils.generate_custom_id("B2B-INW", b2b_inward_products_collection, "inward_id")
        b2b_inward_products_collection.insert_one(doc)
        
    print("Done! Successfully inwarded all variants.")

if __name__ == "__main__":
    run()
