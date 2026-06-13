import sys
from fastapi.testclient import TestClient
from app.main import app
from app.api.b2b_admin_api import B2BInwardOperations
from app import schemas, auth
from app.database import (
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection,
    product_variants_collection,
    b2b_inward_products_collection,
    b2b_cart_collection,
    users_collection
)

def run_cart_tests():
    print("========== STARTING B2B DEALER CART INTEGRATION TESTS ==========")
    client = TestClient(app)

    # 1. Clean up leftovers
    product_categories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_subcategories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_brands_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_models_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_submodels_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_variants_collection.delete_many({"sku_no": {"$regex": "^TEST-B2B"}})
    b2b_inward_products_collection.delete_many({"created_by": "EMP-B2B-TEST-ADMIN"})
    b2b_cart_collection.delete_many({})
    users_collection.delete_many({"email": {"$regex": "^test_dealer.*@example.com"}})

    # 2. Setup Mock Users
    dealer_email = "test_dealer@example.com"
    dealer_id = "DLR-TEST-001"
    
    # Store dealer user in DB
    users_collection.insert_one({
        "user_id": dealer_id,
        "first_name": "Test",
        "last_name": "Dealer",
        "email": dealer_email,
        "mobile_number": "9000000001",
        "role": "Dealer",
        "status": "Active",
        "password_hash": auth.get_password_hash("123")
    })

    # 3. Setup mock master hierarchy
    cat_id = "PCAT-TEST-001"
    subcat_id = "PSUB-TEST-001"
    brand_id = "PBRN-TEST-001"
    model_id = "PMOD-TEST-001"
    submodel_id = "PSMD-TEST-001"
    var1_id = "PVAR-TEST-001"
    var2_id = "PVAR-TEST-002"

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
    product_variants_collection.insert_one({
        "variant_id": var2_id,
        "sku_no": "TEST-B2B-SKU-002",
        "submodel_id": submodel_id,
        "color": "Matte Red",
        "size": 60,
        "size_name": "L",
        "mrp": 3600.0,
        "product_images": [],
        "is_active": True
    })

    # 4. Create B2B Inwards (one active, one inactive)
    current_admin = {
        "user_id": "EMP-B2B-TEST-ADMIN",
        "name": "Test Admin",
        "role": "B2B Admin"
    }
    inward1_schema = schemas.B2BInwardProductCreate(
        variant_id=var1_id,
        dealer_price=3100.0,
        is_individual=True,
        is_carton=False,
        is_featured=True,
        is_active=True
    )
    inward1 = B2BInwardOperations.create_inward(inward1_schema, current_admin)

    inward2_schema = schemas.B2BInwardProductCreate(
        variant_id=var2_id,
        dealer_price=3200.0,
        is_individual=False,
        is_carton=True,
        is_featured=False,
        is_active=False
    )
    inward2 = B2BInwardOperations.create_inward(inward2_schema, current_admin)

    # 5. Generate Auth Token for the Dealer
    token = auth.create_access_token({"sub": dealer_email, "role": "Dealer"})
    headers = {"Authorization": f"Bearer {token}"}

    # 6. Test GET /api/v1/b2b-cart/ (Should be empty initially)
    print("Testing GET /api/v1/b2b-cart/ (initial, empty)...")
    resp = client.get("/api/v1/b2b-cart/", headers=headers)
    assert resp.status_code == 200
    cart = resp.json()
    assert cart["total_items"] == 0
    assert cart["total_price"] == 0.0
    assert len(cart["items"]) == 0
    print("✅ Initial cart is successfully empty!")

    # 7. Test POST /api/v1/b2b-cart/items (Add Variant 1 - Active)
    print("Testing POST /api/v1/b2b-cart/items (Add active inwarded variant)...")
    add_payload = {
        "inward_id": inward1["inward_id"],
        "quantity": 2
    }
    resp = client.post("/api/v1/b2b-cart/items", json=add_payload, headers=headers)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    cart = resp.json()
    assert cart["total_items"] == 2
    assert cart["total_price"] == 6200.0  # 3100.0 * 2
    assert len(cart["items"]) == 1
    
    item = cart["items"][0]
    assert item["inward_id"] == inward1["inward_id"]
    assert item["name"] == "TEST-B2B Brand TEST-B2B Model TEST-B2B Submodel Matte Black M"
    assert item["dealer_price"] == 3100.0
    assert item["mrp"] == 3500.0
    assert item["quantity"] == 2
    assert item["subtotal"] == 6200.0
    print("✅ Item successfully added to cart and resolved dynamically!")

    # 8. Test POST /api/v1/b2b-cart/items (Increment same variant)
    print("Testing incrementing existing cart item...")
    resp = client.post("/api/v1/b2b-cart/items", json={"inward_id": inward1["inward_id"], "quantity": 3}, headers=headers)
    assert resp.status_code == 201
    cart = resp.json()
    assert cart["total_items"] == 5
    assert cart["total_price"] == 15500.0
    assert cart["items"][0]["quantity"] == 5
    print("✅ Existing item quantity correctly incremented!")

    # 9. Test POST /api/v1/b2b-cart/items (Try adding inactive Variant 2)
    print("Testing adding inactive B2B inwarded variant (should be blocked)...")
    resp = client.post("/api/v1/b2b-cart/items", json={"inward_id": inward2["inward_id"], "quantity": 1}, headers=headers)
    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower()
    print("✅ Correctly blocked adding inactive inwarded product!")

    # 10. Test PUT /api/v1/b2b-cart/items/{inward_id} (Update quantity)
    print("Testing updating quantity...")
    resp = client.put(f"/api/v1/b2b-cart/items/{inward1['inward_id']}", json={"quantity": 10}, headers=headers)
    assert resp.status_code == 200
    cart = resp.json()
    assert cart["total_items"] == 10
    assert cart["total_price"] == 31000.0
    assert cart["items"][0]["quantity"] == 10
    print("✅ Cart item quantity updated successfully!")

    # 11. Test PUT /api/v1/b2b-cart/items/{inward_id} to 0 (Deletes item)
    print("Testing setting quantity to 0 (should delete item)...")
    resp = client.put(f"/api/v1/b2b-cart/items/{inward1['inward_id']}", json={"quantity": 0}, headers=headers)
    assert resp.status_code == 200
    cart = resp.json()
    assert cart["total_items"] == 0
    assert len(cart["items"]) == 0
    print("✅ Setting quantity to 0 successfully deletes item from cart!")

    # 12. Test DELETE /api/v1/b2b-cart/items/{inward_id} (Remove item)
    print("Testing deleting item...")
    # Add back first
    client.post("/api/v1/b2b-cart/items", json={"inward_id": inward1["inward_id"], "quantity": 4}, headers=headers)
    
    # Delete
    resp = client.delete(f"/api/v1/b2b-cart/items/{inward1['inward_id']}", headers=headers)
    assert resp.status_code == 200
    cart = resp.json()
    assert cart["total_items"] == 0
    assert len(cart["items"]) == 0
    print("✅ Item deleted successfully!")

    # 13. Test DELETE /api/v1/b2b-cart/ (Clear cart)
    print("Testing clearing cart...")
    # Add back
    client.post("/api/v1/b2b-cart/items", json={"inward_id": inward1["inward_id"], "quantity": 6}, headers=headers)
    
    # Clear
    resp = client.delete("/api/v1/b2b-cart/", headers=headers)
    assert resp.status_code == 200
    cart = resp.json()
    assert cart["total_items"] == 0
    assert len(cart["items"]) == 0
    print("✅ Cart cleared successfully!")

    # 14. Clean up test data
    product_categories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_subcategories_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_brands_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_models_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_submodels_collection.delete_many({"name": {"$regex": "^TEST-B2B"}})
    product_variants_collection.delete_many({"sku_no": {"$regex": "^TEST-B2B"}})
    b2b_inward_products_collection.delete_many({"created_by": "EMP-B2B-TEST-ADMIN"})
    b2b_cart_collection.delete_many({})
    users_collection.delete_many({"email": {"$regex": "^test_dealer.*@example.com"}})

    print("========== ALL B2B DEALER CART INTEGRATION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_cart_tests()
