import sys
import os
from datetime import datetime

# Setup path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import (
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection,
    product_variants_collection,
    b2b_inward_products_collection
)
from app.api.b2b_admin_api import B2BInwardOperations
from app import schemas, utils

def run_tests():
    print("========== STARTING B2B ADMIN API VERIFICATION TESTS ==========")
    
    # 1. Clean up any existing test leftovers
    product_categories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_subcategories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_brands_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_models_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_submodels_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_variants_collection.delete_many({"sku_no": {"$regex": "^TEST-B2B"}})
    b2b_inward_products_collection.delete_many({"created_by": "EMP-B2B-TEST-ADMIN"})

    print("DB leftovers cleaned up successfully.")

    # 2. Create sample Master Product structure
    # A. Category
    cat_id = "PCAT-TEST-001"
    product_categories_collection.insert_one({
        "category_id": cat_id,
        "name": "TEST-B2B Category",
        "is_active": True,
        "created_by": "EMP-B2B-TEST-ADMIN",
        "created_at": datetime.now()
    })
    
    # B. Subcategory
    subcat_id = "PSUB-TEST-001"
    product_subcategories_collection.insert_one({
        "subcategory_id": subcat_id,
        "category_id": cat_id,
        "name": "TEST-B2B Subcategory",
        "is_active": True,
        "created_by": "EMP-B2B-TEST-ADMIN",
        "created_at": datetime.now()
    })

    # C. Brand
    brand_id = "PBRD-TEST-001"
    product_brands_collection.insert_one({
        "brand_id": brand_id,
        "name": "TEST-B2B Brand",
        "description": "Test Brand Description",
        "is_active": True,
        "created_by": "EMP-B2B-TEST-ADMIN",
        "created_at": datetime.now()
    })

    # D. Model
    model_id = "PMOD-TEST-001"
    product_models_collection.insert_one({
        "model_id": model_id,
        "name": "TEST-B2B Model",
        "brand_id": brand_id,
        "category_id": cat_id,
        "subcategory_id": subcat_id,
        "is_active": True,
        "created_by": "EMP-B2B-TEST-ADMIN",
        "created_at": datetime.now()
    })

    # E. Submodel
    submodel_id = "PSMD-TEST-001"
    product_submodels_collection.insert_one({
        "submodel_id": submodel_id,
        "name": "TEST-B2B Submodel Graphic",
        "model_id": model_id,
        "image": "/qrcodes/Submodels/PSMD-TEST-001/image.png",
        "is_active": True,
        "created_by": "EMP-B2B-TEST-ADMIN",
        "created_at": datetime.now()
    })

    # F. Variant 1
    var1_id = "PVAR-TEST-001"
    product_variants_collection.insert_one({
        "variant_id": var1_id,
        "sku_no": "TEST-B2B-SKU-001",
        "submodel_id": submodel_id,
        "color": "Matte Black",
        "size": 58,
        "size_name": "M",
        "finish": "Matte",
        "mrp": 4500.0,
        "product_images": ["/qrcodes/Variants/PVAR-TEST-001/img1.png"],
        "is_active": True
    })

    # G. Variant 2 (Sister Variant under same submodel)
    var2_id = "PVAR-TEST-002"
    product_variants_collection.insert_one({
        "variant_id": var2_id,
        "sku_no": "TEST-B2B-SKU-002",
        "submodel_id": submodel_id,
        "color": "Matte Red",
        "size": 60,
        "size_name": "L",
        "finish": "Glossy",
        "mrp": 4800.0,
        "product_images": [],
        "is_active": True
    })

    print("Master Product hierarchical test data generated successfully.")

    # 3. Test B2B Inwarding Operations
    current_user = {"user_id": "EMP-B2B-TEST-ADMIN", "role": "B2B Admin"}

    # A. Inward Variant 1
    inward_create_schema = schemas.B2BInwardProductCreate(
        variant_id=var1_id,
        dealer_price=3100.0,
        is_individual=True,
        is_carton=False,
        is_featured=True,
        is_new_arrival=True,
        is_best_seller=False,
        is_active=True
    )
    
    inward1 = B2BInwardOperations.create_inward(inward_create_schema, current_user)
    assert inward1["inward_id"].startswith("B2B-INW"), f"Expected custom prefix, got {inward1['inward_id']}"
    assert inward1["sku_no"] == "TEST-B2B-SKU-001", "SKU should match Variant 1 SKU"
    assert inward1["dealer_price"] == 3100.0, "Dealer price should match input"
    assert inward1["is_featured"] is True, "Featured flag should be True"
    assert inward1["is_individual"] is True, "is_individual should be True"
    assert inward1["is_carton"] is False, "is_carton should be False"
    print("✅ Inwarding Product Success")

    # B. Test Duplicate Inward Prevention
    try:
        B2BInwardOperations.create_inward(inward_create_schema, current_user)
        print("❌ Error: Duplicate inward was allowed")
        sys.exit(1)
    except Exception as e:
        print("✅ Duplicate Inward properly blocked (HTTP 400)")

    # C. Test GET All Inwards
    inwards_list = B2BInwardOperations.get_inwards()
    assert len(inwards_list) >= 1, "Should have at least 1 inwarded product"
    
    # Verify nesting of details
    found_item = None
    for item in inwards_list:
        if item["inward_detail"]["inward_id"] == inward1["inward_id"]:
            found_item = item
            break
            
    assert found_item is not None, "Inwarded product not found in list"
    assert found_item["variant_detail"]["sku_no"] == "TEST-B2B-SKU-001", "Nesting failed"
    assert found_item["variant_detail"]["brand_name"] == "TEST-B2B Brand", "Upward brand mapping failed"
    assert found_item["variant_detail"]["category_name"] == "TEST-B2B Category", "Upward category mapping failed"
    print("✅ GET Inwards Listing with Nested Master Product details Success")

    # D. Test GET Card-like Information (High-Performance UI view)
    cards = B2BInwardOperations.get_inward_cards()
    assert len(cards) >= 1, "Should return cards list"
    card_item = next(c for c in cards if c["inward_id"] == inward1["inward_id"])
    
    # Verify card details
    expected_name = "TEST-B2B Brand TEST-B2B Model TEST-B2B Submodel Graphic Matte Black M"
    assert card_item["name"] == expected_name, f"Expected card name '{expected_name}', got '{card_item['name']}'"
    assert card_item["dealer_price"] == 3100.0, "Dealer price mismatch"
    assert card_item["image"] == "/qrcodes/Variants/PVAR-TEST-001/img1.png", "Should fall back to variant's first image"
    print("✅ GET Cards (Lightweight variant-wise representation) Success")

    # E. Inward Variant 2 to see as sister variant with B2B info
    inward2_schema = schemas.B2BInwardProductCreate(
        variant_id=var2_id,
        dealer_price=3300.0,
        is_individual=False,
        is_carton=True,
        is_best_seller=True
    )
    inward2 = B2BInwardOperations.create_inward(inward2_schema, current_user)

    # F. Test GET Details with Sister Variants
    detail_res = B2BInwardOperations.get_inward_detail(inward1["inward_id"])
    assert detail_res["inward_detail"]["inward_id"] == inward1["inward_id"], "Inward details mismatch"
    assert len(detail_res["sister_variants"]) == 1, "Should have 1 sister variant"
    
    sister = detail_res["sister_variants"][0]
    assert sister["variant_id"] == var2_id, "Sister variant ID should be Variant 2"
    assert sister["b2b_inward"] is not None, "Sister variant is B2B inwarded, B2B info should be present"
    assert sister["b2b_inward"]["dealer_price"] == 3300.0, "Sister variant B2B price mismatch"
    print("✅ GET Detail view with complete B2B-aware Sister Variants details Success")

    # G. Test UPDATE B2B properties
    update_schema = schemas.B2BInwardProductUpdate(
        dealer_price=3250.0,
        is_best_seller=True
    )
    updated_inw = B2BInwardOperations.update_inward(inward1["inward_id"], update_schema)
    assert updated_inw["dealer_price"] == 3250.0, "Dealer price was not updated"
    assert updated_inw["is_best_seller"] is True, "is_best_seller flag was not updated"
    print("✅ UPDATE Inward Properties Success")

    # H. Test DELETE Inward product
    del_res1 = B2BInwardOperations.delete_inward(inward1["inward_id"])
    del_res2 = B2BInwardOperations.delete_inward(inward2["inward_id"])
    assert del_res1["status"] == "success", "Failed to delete inward 1"
    
    # Confirm deletion from DB
    assert b2b_inward_products_collection.find_one({"inward_id": inward1["inward_id"]}) is None, "Inward 1 still in DB"
    assert b2b_inward_products_collection.find_one({"inward_id": inward2["inward_id"]}) is None, "Inward 2 still in DB"
    print("✅ DELETE Inward Product Success")

    # 4. Clean up test data
    product_categories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_subcategories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_brands_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_models_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_submodels_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_variants_collection.delete_many({"sku_no": {"$regex": "^TEST-B2B"}})
    print("Test hierarchical data successfully cleaned up from DB.")

    print("\n========== ALL B2B ADMIN API TESTS COMPLETED SUCCESSFULLY! ==========\n")

if __name__ == "__main__":
    run_tests()
