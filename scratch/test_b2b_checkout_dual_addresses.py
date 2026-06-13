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

def run_dual_address_checkout_tests():
    print("========== STARTING B2B DUAL ADDRESS CHECKOUT INTEGRATION TESTS ==========")
    client = TestClient(app)

    dealer_email = "dual_dealer@example.com"
    dealer_id = "DLR-DUAL-TEST"
    inward_id = "B2B-INW-DUAL-MOCK"
    variant_id = "PVAR-DUAL-MOCK"

    # 1. Clean up leftovers
    users_collection.delete_many({"email": dealer_email})
    b2b_cart_collection.delete_many({"user_id": dealer_id})
    b2b_orders_collection.delete_many({"user_id": dealer_id})
    b2b_inward_products_collection.delete_many({"inward_id": inward_id})
    product_variants_collection.delete_many({"variant_id": variant_id})

    # 2. Setup Dealer User
    users_collection.insert_one({
        "user_id": dealer_id,
        "first_name": "Dual",
        "last_name": "Dealer",
        "email": dealer_email,
        "mobile_number": "9999999992",
        "role": "Dealer",
        "status": "Active",
        "password_hash": auth.get_password_hash("123")
    })

    # 3. Generate Auth Token
    token = auth.create_access_token({"sub": dealer_email, "role": "Dealer"})
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Add shipping address
    print("Adding shipping address...")
    shipping_payload = {
        "business_name": "Dual Shipping Inc",
        "address_line": "100 Shipping Road",
        "city": "Port City",
        "state": "Gujarat",
        "pincode": "370001",
        "address_type": "shipping"
    }
    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=shipping_payload, headers=headers)
    assert resp.status_code == 200
    ship_addr = resp.json()
    ship_addr_id = ship_addr["address_id"]
    print("✅ Shipping address registered. ID:", ship_addr_id)

    # 5. Add billing address
    print("Adding billing address...")
    billing_payload = {
        "business_name": "Dual Billing Inc",
        "address_line": "200 Invoice Blvd",
        "city": "Finance City",
        "state": "Maharashtra",
        "pincode": "400001",
        "address_type": "billing"
    }
    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=billing_payload, headers=headers)
    assert resp.status_code == 200
    bill_addr = resp.json()
    bill_addr_id = bill_addr["address_id"]
    print("✅ Billing address registered. ID:", bill_addr_id)

    # 6. Seed active variant & B2B inward
    product_variants_collection.insert_one({
        "variant_id": variant_id,
        "sku_no": "TEST-DUAL-SKU",
        "submodel_id": "PSMD-MOCK",
        "mrp": 5000.0,
        "is_active": True
    })

    b2b_inward_products_collection.insert_one({
        "inward_id": inward_id,
        "variant_id": variant_id,
        "sku_no": "TEST-DUAL-SKU",
        "dealer_price": 3500.0,
        "is_individual": True,
        "is_carton": False,
        "is_active": True,
        "created_by": "EMP-MOCK",
        "created_at": auth.utils.get_current_time(),
        "updated_at": auth.utils.get_current_time()
    })

    # 7. Add item to cart
    print("Adding items to cart...")
    cart_payload = {
        "inward_id": inward_id,
        "quantity": 1
    }
    resp = client.post("/api/v1/b2b-cart/items", json=cart_payload, headers=headers)
    assert resp.status_code == 201

    # 8. Test checkout specifying separate shipping and billing address IDs
    print("Testing checkout specifying both shipping_address_id and billing_address_id...")
    checkout_payload = {
        "shipping_address_id": ship_addr_id,
        "billing_address_id": bill_addr_id
    }
    resp = client.post("/api/v1/b2b-orders/checkout", json=checkout_payload, headers=headers)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    order = resp.json()
    assert order["shipping_address"]["address_id"] == ship_addr_id
    assert order["billing_address"]["address_id"] == bill_addr_id
    assert order["shipping_address"]["business_name"] == "Dual Shipping Inc"
    assert order["billing_address"]["business_name"] == "Dual Billing Inc"
    print("✅ Checkout with explicit dual addresses successful!")

    # 9. Test fallback behavior: checkout without explicit IDs
    # (Should automatically fallback to type "shipping" and "billing" configured on user)
    print("Adding item to cart again for fallback test...")
    resp = client.post("/api/v1/b2b-cart/items", json=cart_payload, headers=headers)
    assert resp.status_code == 201

    print("Testing checkout fallback to configured shipping/billing addresses...")
    resp = client.post("/api/v1/b2b-orders/checkout", json={}, headers=headers)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    order2 = resp.json()
    assert order2["shipping_address"]["address_id"] == ship_addr_id
    assert order2["billing_address"]["address_id"] == bill_addr_id
    print("✅ Checkout fallback to configured shipping and billing addresses successful!")

    # 10. Clean up
    print("Cleaning up mock records...")
    users_collection.delete_many({"email": dealer_email})
    b2b_cart_collection.delete_many({"user_id": dealer_id})
    b2b_orders_collection.delete_many({"user_id": dealer_id})
    b2b_inward_products_collection.delete_many({"inward_id": inward_id})
    product_variants_collection.delete_many({"variant_id": variant_id})

    print("========== ALL B2B DUAL ADDRESS CHECKOUT INTEGRATION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_dual_address_checkout_tests()
