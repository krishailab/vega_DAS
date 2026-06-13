import sys
from fastapi.testclient import TestClient
from app.main import app
from app.api.b2b_admin_api import B2BInwardOperations
from app import schemas
from app.database import (
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection,
    product_variants_collection,
    b2b_inward_products_collection
)

def test_fastapi_endpoints():
    print("========== STARTING B2B ENDPOINT INTEGRATION TESTS ==========")
    client = TestClient(app)

    # 1. Clean up leftovers
    product_categories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_subcategories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_brands_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_models_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_submodels_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_variants_collection.delete_many({"sku_no": {"$regex": "^TEST-B2B"}})
    b2b_inward_products_collection.delete_many({"created_by": "EMP-B2B-TEST-ADMIN"})

    # 2. Setup mock master hierarchy
    cat_id = "PCAT-TEST-001"
    subcat_id = "PSUB-TEST-001"
    brand_id = "PBRN-TEST-001"
    model_id = "PMOD-TEST-001"
    submodel_id = "PSMD-TEST-001"
    var1_id = "PVAR-TEST-001"

    product_categories_collection.insert_one({
        "category_id": cat_id,
        "name": "TEST-B2B Category",
        "is_active": True
    })
    product_subcategories_collection.insert_one({
        "subcategory_id": subcat_id,
        "name": "TEST-B2B Subcategory",
        "category_id": cat_id,
        "is_active": True
    })
    product_brands_collection.insert_one({
        "brand_id": brand_id,
        "name": "TEST-B2B Brand",
        "is_active": True
    })
    product_models_collection.insert_one({
        "model_id": model_id,
        "name": "TEST-B2B Model",
        "brand_id": brand_id,
        "category_id": cat_id,
        "subcategory_id": subcat_id,
        "is_active": True
    })
    product_submodels_collection.insert_one({
        "submodel_id": submodel_id,
        "name": "TEST-B2B Submodel",
        "model_id": model_id,
        "image": "/images/submodels/test.png",
        "is_active": True
    })
    product_variants_collection.insert_one({
        "variant_id": var1_id,
        "sku_no": "TEST-B2B-SKU-001",
        "submodel_id": submodel_id,
        "color": "Matte Black",
        "size": 58,
        "size_name": "M",
        "mrp": 3500.0,
        "product_images": ["/qrcodes/Variants/PVAR-TEST-001/img1.png"],
        "is_active": True
    })

    # 3. Create a B2B Inward via DB operation
    current_user = {
        "user_id": "EMP-B2B-TEST-ADMIN",
        "name": "Test Admin",
        "role": "B2B Admin"
    }
    inward_create_schema = schemas.B2BInwardProductCreate(
        variant_id=var1_id,
        dealer_price=3100.0,
        is_individual=True,
        is_carton=False,
        is_featured=True
    )
    inward1 = B2BInwardOperations.create_inward(inward_create_schema, current_user)

    # 4. Now test the /api/v1/b2b-admin/inwards/cards endpoint (which is public)
    print("Testing GET /api/v1/b2b-admin/inwards/cards ...")
    resp_cards = client.get("/api/v1/b2b-admin/inwards/cards")
    assert resp_cards.status_code == 200, f"Expected 200, got {resp_cards.status_code}"
    cards_list = resp_cards.json()
    assert len(cards_list) >= 1, "Should return at least one card"
    
    card_item = next(c for c in cards_list if c["inward_id"] == inward1["inward_id"])
    assert card_item["name"] == "TEST-B2B Brand TEST-B2B Model TEST-B2B Submodel Matte Black M", "Card name mismatch"
    assert card_item["dealer_price"] == 3100.0
    print("✅ /inwards/cards endpoint returns correct lightweight data!")

    # 5. Let's obtain a valid authentication token or mock auth to test GET /api/v1/b2b-admin/inwards/
    # Wait, the auth system uses JWT. We can generate a token or bypass it. Let's see how jwt is done in app.auth.
    from app import auth
    # Super Admin Karan@vega.com is in DB. We can fetch or use standard admin credentials.
    # Let's try log in via /api/v1/auth/login or /api/v1/token or similar if it exists.
    # Let's search how token login is tested.
    # Actually we can just generate a token directly!
    token = auth.create_access_token({"sub": "b2badmin@vega.com", "role": "B2B Admin"})
    headers = {"Authorization": f"Bearer {token}"}

    print("Testing GET /api/v1/b2b-admin/inwards/ (should return 405 Method Not Allowed) ...")
    resp_inwards = client.get("/api/v1/b2b-admin/inwards/", headers=headers)
    assert resp_inwards.status_code == 405, f"Expected 405 Method Not Allowed, got {resp_inwards.status_code}"
    print("✅ /inwards/ endpoint successfully removed (returns 405)!")

    # 6. Test GET /api/v1/b2b-admin/inwards/{inward_id} (public access without headers)
    print("Testing GET /api/v1/b2b-admin/inwards/{inward_id} (without authentication) ...")
    resp_detail = client.get(f"/api/v1/b2b-admin/inwards/{inward1['inward_id']}")
    assert resp_detail.status_code == 200, f"Expected 200, got {resp_detail.status_code}"
    detail_data = resp_detail.json()
    assert detail_data["inward_detail"]["inward_id"] == inward1["inward_id"]
    assert detail_data["variant_detail"]["sku_no"] == "TEST-B2B-SKU-001"
    print("✅ /inwards/{inward_id} endpoint successfully accessed anonymously (public)!")

    # Clean up test data
    product_categories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_subcategories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_brands_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_models_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_submodels_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_variants_collection.delete_many({"sku_no": {"$regex": "^TEST-B2B"}})
    b2b_inward_products_collection.delete_many({"created_by": "EMP-B2B-TEST-ADMIN"})

    print("========== ALL B2B ENDPOINT INTEGRATION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    test_fastapi_endpoints()
