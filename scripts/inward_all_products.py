import os
import sys

# Add the parent directory to sys.path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import (
    product_variants_collection,
    b2b_inward_products_collection
)
from app.utils import generate_custom_id, get_current_time

def inward_all_products():
    print("Fetching active product variants...")
    variants = list(product_variants_collection.find({"is_active": True}))
    print(f"Found {len(variants)} active product variants.")
    
    added_count = 0
    skipped_count = 0
    for variant in variants:
        variant_id = variant["variant_id"]
        sku_no = variant.get("sku_no")
        
        # Check if already inwarded
        existing = b2b_inward_products_collection.find_one({"variant_id": variant_id})
        if existing:
            skipped_count += 1
            continue
            
        inward_id = generate_custom_id("B2B-INW", b2b_inward_products_collection, "inward_id")
        now = get_current_time()
        
        # Default dealer price calculation (e.g., MRP * 0.75, or 0.0 if not available)
        mrp_raw = variant.get("mrp")
        mrp_val = 0.0
        if isinstance(mrp_raw, dict):
            mrp_val = mrp_raw.get("INR", 0.0)
            if not mrp_val and mrp_raw:
                mrp_val = next(iter(mrp_raw.values()), 0.0)
        elif isinstance(mrp_raw, (int, float)):
            mrp_val = float(mrp_raw)

        dealer_price = float(mrp_val) * 0.75
        
        inward_doc = {
            "inward_id": inward_id,
            "variant_id": variant_id,
            "sku_no": sku_no,
            "dealer_price": dealer_price,
            "currency": "INR",
            "is_individual": True,
            "is_carton": False,
            "is_featured": False,
            "is_new_arrival": False,
            "is_best_seller": False,
            "is_active": True,
            "created_by": "system_init_script",
            "created_at": now,
            "updated_at": now
        }
        
        b2b_inward_products_collection.insert_one(inward_doc)
        added_count += 1
        
    print(f"Skipped {skipped_count} products (already inwarded).")
    print(f"Successfully inwarded {added_count} new products.")

if __name__ == "__main__":
    inward_all_products()
