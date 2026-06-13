import sys
from fastapi.testclient import TestClient
from app.main import app
from app import auth
from app.database import (
    users_collection,
    b2b_cart_collection,
    b2b_orders_collection,
    b2b_inward_products_collection,
    product_variants_collection
)

def run_checkout_tests():
    print("========== STARTING B2B DEALER CHECKOUT INTEGRATION TESTS ==========")
    client = TestClient(app)

    dealer_email = "checkout_dealer@example.com"
    dealer_id = "DLR-CHKT-TEST-01"
    inward_id = "B2B-INW-TEST-99"
    variant_id = "PVAR-TEST-99"

    # 1. Clean up leftovers
    users_collection.delete_many({"email": dealer_email})
    b2b_cart_collection.delete_many({"user_id": dealer_id})
    b2b_orders_collection.delete_many({"user_id": dealer_id})
    b2b_inward_products_collection.delete_many({"inward_id": inward_id})
    product_variants_collection.delete_many({"variant_id": variant_id})

    # 2. Setup Dealer User (With no address initially)
    users_collection.insert_one({
        "user_id": dealer_id,
        "first_name": "Checkout",
        "last_name": "Dealer",
        "email": dealer_email,
        "mobile_number": "9222222222",
        "role": "Dealer",
        "status": "Active",
        "password_hash": auth.get_password_hash("123")
    })

    # 3. Generate Auth Token
    token = auth.create_access_token({"sub": dealer_email, "role": "Dealer"})
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Test checkout with missing address (should be 400 Bad Request)
    print("Testing checkout with missing company address (should be 400)...")
    resp = client.post("/api/v1/b2b-orders/checkout", headers=headers)
    assert resp.status_code == 400
    assert "company address" in resp.json()["detail"].lower()
    print("✅ Successfully blocked checkout when company address is missing!")

    # 5. Add Company Address using API
    print("Adding first company address to dealer profile...")
    address_payload = {
        "business_name": "Acme Orders Ltd",
        "address_line": "123 Order Expressway, Suite 4",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
        "gstin": "29AAAAA2222A2Z1",
        "alternate_mobile": "9876543211"
    }
    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=address_payload, headers=headers)
    assert resp.status_code == 200
    addr1 = resp.json()
    addr1_id = addr1["address_id"]
    print("✅ Registered first company address successfully! ID:", addr1_id)

    print("Adding second company address to dealer profile...")
    address_payload_2 = {
        "business_name": "Acme Orders Branch 2",
        "address_line": "555 Southern Blvd",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "pincode": "600001",
        "gstin": "33AAAAA3333A3Z3",
        "alternate_mobile": "9876543222"
    }
    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=address_payload_2, headers=headers)
    assert resp.status_code == 200
    addr2 = resp.json()
    addr2_id = addr2["address_id"]
    print("✅ Registered second company address successfully! ID:", addr2_id)

    # 6. Test checkout with empty cart (should be 400 Bad Request)
    print("Testing checkout with empty shopping cart (should be 400)...")
    resp = client.post("/api/v1/b2b-orders/checkout", headers=headers)
    assert resp.status_code == 400
    assert "cart is empty" in resp.json()["detail"].lower()
    print("✅ Successfully blocked checkout when shopping cart is empty!")

    # 7. Seed active variant & B2B inward
    print("Seeding test product variant and B2B inward catalog item...")
    product_variants_collection.insert_one({
        "variant_id": variant_id,
        "sku_no": "TEST-HELMET-SKU-99",
        "submodel_id": "PSMD-MOCK",
        "color": "Glossy Red",
        "size_name": "L",
        "size": 60,
        "mrp": 5000.0,
        "is_active": True
    })

    b2b_inward_products_collection.insert_one({
        "inward_id": inward_id,
        "variant_id": variant_id,
        "sku_no": "TEST-HELMET-SKU-99",
        "dealer_price": 3500.0,
        "is_individual": True,
        "is_carton": False,
        "is_featured": True,
        "is_active": True,
        "created_by": "EMP-MOCK",
        "created_at": auth.utils.get_current_time(),
        "updated_at": auth.utils.get_current_time()
    })

    # 8. Add item to dealer's cart
    print("Adding item to cart...")
    cart_payload = {
        "inward_id": inward_id,
        "quantity": 2
    }
    resp = client.post("/api/v1/b2b-cart/items", json=cart_payload, headers=headers)
    assert resp.status_code == 201
    print("✅ Successfully added items to cart!")

    # Test checkout with non-existent address_id (should be 400 Bad Request)
    print("Testing checkout with non-existent address_id (should be 400)...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={"address_id": "ADDR-INVALID999"}, headers=headers)
    assert resp.status_code == 400
    assert "not found on dealer profile" in resp.json()["detail"].lower()
    print("✅ Successfully blocked checkout when passing an invalid address_id!")

    # 9. Perform default checkout (should fallback to primary address: addr1)
    print("Testing checkout with empty JSON body / no address_id (should fallback to primary)...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={}, headers=headers)
    assert resp.status_code == 201, f"Checkout failed: {resp.text}"
    order = resp.json()
    assert order["order_id"].startswith("B2B-ORD")
    assert order["user_id"] == dealer_id
    assert order["company_address"]["business_name"] == "Acme Orders Ltd"
    assert order["company_address"]["pincode"] == "560001"
    assert order["company_address"]["address_id"] == addr1_id
    assert len(order["items"]) == 1
    assert order["items"][0]["inward_id"] == inward_id
    assert order["items"][0]["quantity"] == 2
    assert order["items"][0]["dealer_price"] == 3500.0
    assert order["total_items"] == 2
    assert order["total_price"] == 7000.0
    assert order["status"] == "Pending"
    print("✅ Default checkout successful with primary address! Order ID:", order["order_id"])

    # Verify cart is empty in MongoDB
    db_cart_count = b2b_cart_collection.count_documents({"user_id": dealer_id})
    assert db_cart_count == 0
    print("✅ Verified cart is completely cleared in database!")

    # Add item to dealer's cart again for the second checkout
    print("Adding item to cart again...")
    resp = client.post("/api/v1/b2b-cart/items", json=cart_payload, headers=headers)
    assert resp.status_code == 201

    # Perform checkout with second address_id
    print("Testing checkout with specific address_id = second address (should capture second address)...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={"address_id": addr2_id}, headers=headers)
    assert resp.status_code == 201, f"Checkout failed: {resp.text}"
    order2 = resp.json()
    assert order2["order_id"].startswith("B2B-ORD")
    assert order2["user_id"] == dealer_id
    assert order2["company_address"]["business_name"] == "Acme Orders Branch 2"
    assert order2["company_address"]["pincode"] == "600001"
    assert order2["company_address"]["address_id"] == addr2_id
    print("✅ Selected address checkout successful! Order ID:", order2["order_id"])

    # Verify cart is empty via GET cart API
    resp = client.get("/api/v1/b2b-cart/", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_items"] == 0
    assert len(resp.json()["items"]) == 0
    print("✅ Verified cart retrieval API returns empty cart!")

    # 10. Retrieve orders list
    print("Retrieving all orders for dealer (summary view)...")
    resp = client.get("/api/v1/b2b-orders/", headers=headers)
    assert resp.status_code == 200
    orders_list = resp.json()
    assert len(orders_list) == 2
    order_ids = [o["order_id"] for o in orders_list]
    assert order["order_id"] in order_ids
    assert order2["order_id"] in order_ids
    # Verify summary fields — no items array but address and ordered_by present
    for o in orders_list:
        assert "order_id" in o
        assert "total_items" in o
        assert "total_price" in o
        assert "status" in o
        assert "created_at" in o
        assert "ordered_by" in o
        assert "company_address" in o
        assert "items" not in o
    print("✅ Successfully retrieved orders summary list with ordered_by + address!")

    # Retrieve specific order (full detail)
    print("Retrieving specific order by ID (full detail)...")
    resp = client.get(f"/api/v1/b2b-orders/{order2['order_id']}", headers=headers)
    assert resp.status_code == 200
    single_order = resp.json()
    assert single_order["order_id"] == order2["order_id"]
    assert single_order["total_price"] == 7000.0
    assert "company_address" in single_order
    assert "items" in single_order
    print("✅ Successfully retrieved specific order with full detail (address + items)!")

    # 11. Clean up
    print("Cleaning up mock records...")
    users_collection.delete_many({"email": dealer_email})
    b2b_cart_collection.delete_many({"user_id": dealer_id})
    b2b_orders_collection.delete_many({"user_id": dealer_id})
    b2b_inward_products_collection.delete_many({"inward_id": inward_id})
    product_variants_collection.delete_many({"variant_id": variant_id})

    print("========== ALL B2B CHECKOUT INTEGRATION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_checkout_tests()
