import sys
from fastapi.testclient import TestClient
from app.main import app
from app import auth
from app.database import users_collection, dealer_signup_requests_collection

def run_dealer_address_protection_tests():
    print("========== STARTING B2B DEALER ADDRESS PROTECTION INTEGRATION TESTS ==========")
    client = TestClient(app)

    # 1. Clean up leftovers
    dealer_email = "protection_dealer@example.com"
    admin_email = "protection_admin@example.com"
    
    users_collection.delete_many({"email": {"$in": [dealer_email, admin_email]}})
    dealer_signup_requests_collection.delete_many({"email": dealer_email})

    # 2. Setup Super Admin User for approving signup
    admin_id = "ADMIN-PROT-TEST"
    users_collection.insert_one({
        "user_id": admin_id,
        "first_name": "Prot",
        "last_name": "Admin",
        "email": admin_email,
        "role": "Super Admin",
        "status": "Active",
        "password_hash": auth.get_password_hash("123")
    })

    admin_token = auth.create_access_token({"sub": admin_email, "role": "Super Admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Submit Dealer Signup Request with reorganized fields
    print("Submitting dealer signup request with reorganized fields...")
    signup_payload = {
        "contact_name": "Protection Dealer",
        "email": dealer_email,
        "mobile_number": "9222222222",
        "business_name": "Safe Trade Corp",
        "business_email": "safetrade@example.com",
        "business_mobile": "9333333333",
        "address": "123 Secure Boulevard",
        "city": "Cyber City",
        "state": "Telangana",
        "pincode": "500081",
        "web": "https://safetrade.example.com",
        "gstin": "36AAAAA1111A1Z9",
        "alternate_mobile_number": "9444444444",
        "comments": "Requesting dealer verification."
    }

    resp = client.post("/dealer-signups/", json=signup_payload)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    signup_data = resp.json()
    assert signup_data["status"] == "Pending"
    assert signup_data["contact_name"] == "Protection Dealer"
    assert signup_data["business_email"] == "safetrade@example.com"
    assert signup_data["web"] == "https://safetrade.example.com"
    assert signup_data["gstin"] == "36AAAAA1111A1Z9"
    request_id = signup_data["request_id"]
    print("✅ Dealer signup request successfully submitted!")

    # 4. Approve the signup request
    print(f"Approving dealer signup request {request_id}...")
    approve_payload = {
        "approve": True,
        "password": "DealerPassword123"
    }
    resp = client.put(f"/dealer-signups/{request_id}/status", json=approve_payload, headers=admin_headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["status"] == "Approved"
    print("✅ Dealer signup successfully approved!")

    # 5. Verify the dealer user exists in the database
    dealer_user = users_collection.find_one({"email": dealer_email})
    assert dealer_user is not None
    assert dealer_user["role"] == "Dealer"
    assert "company_address" in dealer_user
    comp_addr = dealer_user["company_address"]
    assert comp_addr["is_business_address"] is True
    assert comp_addr["address_type"] == "business"
    assert comp_addr["web"] == "https://safetrade.example.com"
    assert comp_addr["gstin"] == "36AAAAA1111A1Z9"
    assert comp_addr["business_email"] == "safetrade@example.com"
    assert comp_addr["business_mobile"] == "9333333333"
    print("✅ Verified dealer account creation, address fields, address_type, and is_business_address flag!")

    # 6. Authenticate as Dealer
    dealer_token = auth.create_access_token({"sub": dealer_email, "role": "Dealer"})
    dealer_headers = {"Authorization": f"Bearer {dealer_token}"}

    # 7. Call GET /api/v1/b2b-dealer/company/addresses
    print("Fetching company addresses list for the dealer...")
    resp = client.get("/api/v1/b2b-dealer/company/addresses", headers=dealer_headers)
    assert resp.status_code == 200
    addresses = resp.json()
    assert len(addresses) == 1
    business_addr = addresses[0]
    assert business_addr["is_business_address"] is True
    assert business_addr["address_type"] == "business"
    assert business_addr["web"] == "https://safetrade.example.com"
    business_addr_id = business_addr["address_id"]
    print("✅ Successfully verified GET endpoint returns business address with web field and address_type!")

    # 8. Try to delete the business address (should fail with 400)
    print("Attempting to delete the business address...")
    resp = client.delete(f"/api/v1/b2b-dealer/company/addresses/{business_addr_id}", headers=dealer_headers)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "business address is not deletable" in resp.json()["detail"].lower()
    print("✅ Successfully verified deletion is blocked!")

    # 9. Add a secondary address
    print("Adding a secondary address...")
    secondary_payload = {
        "business_name": "Safe Trade Warehouse",
        "address_line": "456 Storage Road",
        "city": "Cyber City",
        "state": "Telangana",
        "pincode": "500081",
        "gstin": "36AAAAA1111A1Z9",
        "alternate_mobile": "9999999999",
        "address_type": "billing"
    }
    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=secondary_payload, headers=dealer_headers)
    assert resp.status_code == 200
    sec_addr = resp.json()
    assert sec_addr.get("is_business_address") is False or sec_addr.get("is_business_address") is None
    assert sec_addr.get("address_type") == "billing"
    sec_addr_id = sec_addr["address_id"]
    print("✅ Successfully added secondary address with address_type 'billing'!")

    # 10. Attempt to delete the secondary address (should succeed)
    print("Attempting to delete the secondary address...")
    resp = client.delete(f"/api/v1/b2b-dealer/company/addresses/{sec_addr_id}", headers=dealer_headers)
    assert resp.status_code == 200
    print("✅ Successfully deleted secondary address!")

    # 11. Cleanup test data
    users_collection.delete_many({"email": {"$in": [dealer_email, admin_email]}})
    dealer_signup_requests_collection.delete_many({"email": dealer_email})
    print("========== ALL ADDRESS PROTECTION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_dealer_address_protection_tests()
