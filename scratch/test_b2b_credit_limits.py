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

def run_credit_limit_tests():
    print("========== STARTING B2B CREDIT LIMIT INTEGRATION TESTS ==========")
    client = TestClient(app)

    dealer_email = "credit_dealer@example.com"
    dealer_id = "DLR-CREDIT-TEST"
    inward_id = "B2B-INW-CREDIT-MOCK"
    variant_id = "PVAR-CREDIT-MOCK"

    # 1. Clean up leftovers
    users_collection.delete_many({"email": dealer_email})
    b2b_cart_collection.delete_many({"user_id": dealer_id})
    b2b_orders_collection.delete_many({"user_id": dealer_id})
    b2b_inward_products_collection.delete_many({"inward_id": inward_id})
    product_variants_collection.delete_many({"variant_id": variant_id})

    # 2. Setup Dealer User with company address
    address = {
        "address_id": "ADDR-CREDIT-1",
        "business_name": "Credit Check Ltd",
        "address_line": "999 Limits Ave",
        "city": "Capital",
        "state": "Delhi",
        "pincode": "110001",
        "is_business_address": True
    }
    users_collection.insert_one({
        "user_id": dealer_id,
        "first_name": "Credit",
        "last_name": "Dealer",
        "email": dealer_email,
        "mobile_number": "9999999991",
        "role": "Dealer",
        "status": "Active",
        "password_hash": auth.get_password_hash("123"),
        "company_address": address,
        "company_addresses": [address],
        "order_credit_limit": 5000.0,      # Max 5,000 per order initially
        "overall_credit_limit": 10000.0    # Max 10,000 overall outstanding
    })

    # 3. Generate Auth Token
    token = auth.create_access_token({"sub": dealer_email, "role": "Dealer"})
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Seed active variant & B2B inward
    product_variants_collection.insert_one({
        "variant_id": variant_id,
        "sku_no": "TEST-CREDIT-SKU",
        "submodel_id": "PSMD-MOCK",
        "mrp": 5000.0,
        "is_active": True
    })

    b2b_inward_products_collection.insert_one({
        "inward_id": inward_id,
        "variant_id": variant_id,
        "sku_no": "TEST-CREDIT-SKU",
        "dealer_price": 3500.0,
        "is_individual": True,
        "is_carton": False,
        "is_active": True,
        "created_by": "EMP-MOCK",
        "created_at": auth.utils.get_current_time(),
        "updated_at": auth.utils.get_current_time()
    })

    # 5. Add 2 items worth 7000.0 total to cart
    print("Adding 2 items worth 7000.0 total to cart...")
    cart_payload = {
        "inward_id": inward_id,
        "quantity": 2
    }
    resp = client.post("/api/v1/b2b-cart/items", json=cart_payload, headers=headers)
    assert resp.status_code == 201

    # 6. Attempt checkout: Order is 7000.0, order limit is 5000.0 (should fail)
    print("Testing checkout exceeding single order credit limit (should fail with 400)...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={}, headers=headers)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "exceeds the single order credit limit" in resp.json()["detail"].lower()
    print("✅ Successfully blocked checkout exceeding single order credit limit!")

    # 7. Update order limit to 10000.0
    print("Increasing dealer's order_credit_limit to 10000.0...")
    users_collection.update_one({"user_id": dealer_id}, {"$set": {"order_credit_limit": 10000.0}})

    # 8. Attempt checkout: Should succeed now (7000.0 <= 10000.0 order limit, 7000.0 <= 10000.0 overall limit)
    print("Testing checkout within updated single order limit...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={}, headers=headers)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    order1 = resp.json()
    assert order1["total_price"] == 7000.0
    print("✅ Checkout successful! Order ID:", order1["order_id"])

    # 9. Add 1 item worth 3500.0 to cart (outstanding is 7000.0, overall limit is 10000.0, current total will be 10500.0)
    print("Adding 1 item worth 3500.0 to cart again...")
    cart_payload_2 = {
        "inward_id": inward_id,
        "quantity": 1
    }
    resp = client.post("/api/v1/b2b-cart/items", json=cart_payload_2, headers=headers)
    assert resp.status_code == 201

    # 10. Attempt checkout (should fail as outstanding 7000 + 3500 = 10500 exceeds 10000 limit)
    print("Testing checkout exceeding overall credit limit (should fail with 400)...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={}, headers=headers)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "exceeds the overall credit limit" in resp.json()["detail"].lower()
    print("✅ Successfully blocked checkout exceeding overall credit limit!")

    # 11. Increase overall credit limit to 20000.0
    print("Increasing dealer's overall_credit_limit to 20000.0...")
    users_collection.update_one({"user_id": dealer_id}, {"$set": {"overall_credit_limit": 20000.0}})

    # 12. Attempt checkout: Should succeed now (10500 <= 20000)
    print("Testing checkout within updated overall credit limit...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={}, headers=headers)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    order2 = resp.json()
    assert order2["total_price"] == 3500.0
    print("✅ Checkout successful! Order ID:", order2["order_id"])

    # 12.5 Test security validation: Dealer attempting to modify their own credit limit (should be blocked with 403)
    print("Testing Dealer attempting to modify their own order_credit_limit (should fail with 403)...")
    update_payload = {
        "order_credit_limit": 999999.0
    }
    resp = client.put(f"/users/{dealer_id}", json=update_payload, headers=headers)
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    assert "not authorized to update" in resp.json()["detail"].lower()
    print("✅ Successfully verified Dealer is blocked from self-updating credit limits!")

    # 13. Clean up test data
    print("Cleaning up mock records...")
    users_collection.delete_many({"email": dealer_email})
    b2b_cart_collection.delete_many({"user_id": dealer_id})
    b2b_orders_collection.delete_many({"user_id": dealer_id})
    b2b_inward_products_collection.delete_many({"inward_id": inward_id})
    product_variants_collection.delete_many({"variant_id": variant_id})

    print("========== ALL B2B CREDIT LIMIT INTEGRATION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_credit_limit_tests()
