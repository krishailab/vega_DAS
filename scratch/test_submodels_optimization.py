import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.product_api import ProductSubModelOperations

def test_get_submodels():
    print("Testing get_submodels execution and payload structure...")
    
    start_time = time.perf_counter()
    res = ProductSubModelOperations.get_submodels(page=1, limit=50)
    duration = time.perf_counter() - start_time
    
    # Assert pagination keys
    assert "total" in res, "Expected 'total' in response"
    assert "page" in res, "Expected 'page' in response"
    assert "limit" in res, "Expected 'limit' in response"
    assert "pages" in res, "Expected 'pages' in response"
    assert "submodels" in res, "Expected 'submodels' in response"
    
    submodels = res["submodels"]
    print(f"Retrieved {len(submodels)} submodels in {duration:.4f} seconds (Total in DB: {res['total']}).")
    
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
    
    # Run new custom variant test
    from app.schemas import ProductSubModelCreate
    from app.database import product_submodels_collection, product_variants_collection
    
    def test_create_submodel_with_custom_variants():
        print("\nTesting creation of submodel with custom variant colors and images...")
        admin_user = {"user_id": "admin_01", "role": "Super Admin"}
        
        submodel_name = "Automated Test Graphic Color-Wise"
        
        # Clean any leftover test submodel
        product_submodels_collection.delete_many({"name": submodel_name})
        product_variants_collection.delete_many({"sku_no": {"$in": ["SKU-TEST-1", "SKU-TEST-2", "SKU-TEST-3"]}})
        
        submodel_schema = ProductSubModelCreate(
            name=submodel_name,
            model_id="PMOD26A0001",
            is_active=True,
            product_images=["sub_img1.png"]
        )
        
        parsed_variants = [
            ["S", 56, "SKU-TEST-1"],
            ["M", 58, "SKU-TEST-2", "CUSTOM_RED"],
            ["L", 60, "SKU-TEST-3", "CUSTOM_BLUE", ["custom_blue_1.png", "custom_blue_2.png"]]
        ]
        
        res = ProductSubModelOperations.create_submodel(
            submodel=submodel_schema,
            image_file=None,
            images=["sub_img1.png"],
            certification=[],
            parsed_variants=parsed_variants,
            current_user=admin_user
        )
        
        submodel_id = res["submodel_id"]
        variants = res.get("variants", [])
        assert len(variants) == 3, f"Expected 3 variants, got {len(variants)}"
        
        v1 = next(v for v in variants if v["sku_no"] == "SKU-TEST-1")
        v2 = next(v for v in variants if v["sku_no"] == "SKU-TEST-2")
        v3 = next(v for v in variants if v["sku_no"] == "SKU-TEST-3")
        
        assert v1["color"] is None, f"Expected None color, got {v1['color']}"
        assert v1["product_images"] == ["sub_img1.png"], f"Expected default images, got {v1['product_images']}"
        
        assert v2["color"] == "CUSTOM_RED", f"Expected CUSTOM_RED, got {v2['color']}"
        assert v2["product_images"] == ["sub_img1.png"], f"Expected default images, got {v2['product_images']}"
        
        assert v3["color"] == "CUSTOM_BLUE", f"Expected CUSTOM_BLUE, got {v3['color']}"
        assert v3["product_images"] == ["custom_blue_1.png", "custom_blue_2.png"], f"Expected custom images, got {v3['product_images']}"
        
        print("✓ Success: Custom variant colors and images parsed and created successfully!")
        
        # Clean up
        product_submodels_collection.delete_many({"submodel_id": submodel_id})
        product_variants_collection.delete_many({"submodel_id": submodel_id})

    test_create_submodel_with_custom_variants()

