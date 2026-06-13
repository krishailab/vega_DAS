import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.product_api import ProductSubModelOperations

def test_get_submodels():
    print("Testing get_submodels execution and payload structure...")
    
    start_time = time.perf_counter()
    submodels = ProductSubModelOperations.get_submodels(page=1, limit=50)
    duration = time.perf_counter() - start_time
    
    print(f"Retrieved {len(submodels)} submodels in {duration:.4f} seconds.")
    
    if not submodels:
        print("No submodels found. Please ensure there is some data in the database.")
        return

    # Check the first submodel structure
    first_submodel = submodels[0]
    print(f"\nSubmodel ID: {first_submodel.get('submodel_id')}")
    print(f"Submodel Name: {first_submodel.get('name')}")
    
    variants = first_submodel.get("variants", [])
    print(f"Number of nested variants: {len(variants)}")
    
    if variants:
        first_variant = variants[0]
        print(f"First variant payload: {first_variant}")
        
        # Verify keys
        allowed_keys = {"variant_id", "sku_no", "size", "size_name", "color", "product_images"}
        variant_keys = set(first_variant.keys())
        
        extra_keys = variant_keys - allowed_keys
        missing_keys = allowed_keys - variant_keys
        
        if extra_keys:
            print(f"❌ Failure: Variant payload has extra keys: {extra_keys}")
        elif missing_keys:
            print(f"❌ Failure: Variant payload is missing keys: {missing_keys}")
        else:
            print("✓ Success: Variant payload contains exactly the expected keys!")
    else:
        print("No nested variants found in this submodel to verify.")

if __name__ == "__main__":
    test_get_submodels()
