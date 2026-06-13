import sys
from fastapi.testclient import TestClient
from app.main import app
from app import auth
from app.database import users_collection

def run_dealer_address_tests():
    print("========== STARTING B2B DEALER COMPANY ADDRESS INTEGRATION TESTS ==========")
    client = TestClient(app)

    # 1. Clean up leftovers
    dealer_email = "addr_dealer@example.com"
    dealer_id = "DLR-ADDR-TEST-01"
    users_collection.delete_many({"email": dealer_email})

    # 2. Setup Dealer User
    users_collection.insert_one({
        "user_id": dealer_id,
        "first_name": "Address",
        "last_name": "Dealer",
        "email": dealer_email,
        "mobile_number": "9111111111",
        "role": "Dealer",
        "status": "Active",
        "password_hash": auth.get_password_hash("123")
    })

    # 3. Generate Auth Token
    token = auth.create_access_token({"sub": dealer_email, "role": "Dealer"})
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Test GET /company/addresses (Initial state, should be empty list)
    print("Testing GET /api/v1/b2b-dealer/company/addresses (initial, should be [])...")
    resp = client.get("/api/v1/b2b-dealer/company/addresses", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []
    print("✅ Successfully verified empty company addresses list!")

    # 5. Test POST /company/addresses (Add address)
    print("Testing POST /api/v1/b2b-dealer/company/addresses (Create address)...")
    payload = {
        "business_name": "Acme Track Ltd",
        "address_line": "456 Safety Highway, Zone 3",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001",
        "gstin": "27AAAAA1111A1Z0",
        "alternate_mobile": "9876543210"
    }
    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=payload, headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    addr = resp.json()
    assert addr["business_name"] == "Acme Track Ltd"
    assert addr["address_line"] == "456 Safety Highway, Zone 3"
    assert addr["city"] == "Mumbai"
    assert addr["state"] == "Maharashtra"
    assert addr["pincode"] == "400001"
    assert addr["gstin"] == "27AAAAA1111A1Z0"
    assert addr["alternate_mobile"] == "9876543210"
    assert addr["user_id"] == dealer_id
    assert "updated_at" in addr
    print("✅ Company address successfully added via POST /company/addresses!")

    # Verify directly in MongoDB
    db_user = users_collection.find_one({"user_id": dealer_id})
    assert db_user is not None
    assert "company_address" in db_user
    assert db_user["company_address"]["business_name"] == "Acme Track Ltd"
    assert db_user["company_address"]["pincode"] == "400001"
    print("✅ Verified address successfully persisted inside user document in MongoDB!")

    # 6. Test GET /company/addresses (After creation, should be list with 1 item)
    print("Testing GET /api/v1/b2b-dealer/company/addresses (after creation, should be 200)...")
    resp = client.get("/api/v1/b2b-dealer/company/addresses", headers=headers)
    assert resp.status_code == 200
    addresses_list = resp.json()
    assert len(addresses_list) == 1
    addr = addresses_list[0]
    assert addr["business_name"] == "Acme Track Ltd"
    assert addr["city"] == "Mumbai"
    print("✅ Successfully retrieved saved company address list!")

    # 7. Test POST /company/addresses (Update address)
    print("Testing POST /api/v1/b2b-dealer/company/addresses (Update existing)...")
    update_payload = dict(payload)
    update_payload["business_name"] = "Acme Track Globals"
    update_payload["city"] = "Pune"
    update_payload["address_id"] = addr.get("address_id")

    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=update_payload, headers=headers)
    assert resp.status_code == 200
    addr = resp.json()
    assert addr["business_name"] == "Acme Track Globals"
    assert addr["city"] == "Pune"
    
    # Verify in DB
    db_user = users_collection.find_one({"user_id": dealer_id})
    assert db_user["company_address"]["business_name"] == "Acme Track Globals"
    assert db_user["company_address"]["city"] == "Pune"
    print("✅ Company address updated successfully via POST /company/addresses!")

    # 7.5 Test Multiple Address Support (Append additional address)
    print("Testing adding multiple company addresses...")
    
    # Assert first address has an ID
    assert addr.get("address_id") is not None
    addr1_id = addr["address_id"]
    
    # Get all addresses (should be 1)
    resp = client.get("/api/v1/b2b-dealer/company/addresses", headers=headers)
    assert resp.status_code == 200
    addresses_list = resp.json()
    assert len(addresses_list) == 1
    assert addresses_list[0]["address_id"] == addr1_id
    
    # Add second address using the new plural POST endpoint
    payload_2 = {
        "business_name": "Acme Track Southern Branch",
        "address_line": "789 Southern Highway, Zone 5",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
        "gstin": "29AAAAA2222A2Z2",
        "alternate_mobile": "9999999999"
    }
    resp = client.post("/api/v1/b2b-dealer/company/addresses", json=payload_2, headers=headers)
    assert resp.status_code == 200
    addr2 = resp.json()
    assert addr2.get("address_id") is not None
    assert addr2["address_id"] != addr1_id
    addr2_id = addr2["address_id"]
    print("✅ Second company address successfully added via POST /company/addresses!")

    # Retrieve all addresses (should be 2)
    resp = client.get("/api/v1/b2b-dealer/company/addresses", headers=headers)
    assert resp.status_code == 200
    addresses_list = resp.json()
    assert len(addresses_list) == 2
    assert addresses_list[0]["address_id"] == addr1_id
    assert addresses_list[1]["address_id"] == addr2_id
    print("✅ Verified list retrieve returns all registered addresses!")

    # Test Deleting Address 2 using the new plural DELETE endpoint
    print("Testing deleting second company address via DELETE /company/addresses/{address_id}...")
    resp = client.delete(f"/api/v1/b2b-dealer/company/addresses/{addr2_id}", headers=headers)
    assert resp.status_code == 200
    assert "deleted successfully" in resp.json()["detail"].lower()
    
    # Retrieve all addresses (should be 1 again)
    resp = client.get("/api/v1/b2b-dealer/company/addresses", headers=headers)
    assert resp.status_code == 200
    addresses_list = resp.json()
    assert len(addresses_list) == 1
    assert addresses_list[0]["address_id"] == addr1_id
    print("✅ Successfully deleted second address and confirmed deletion!")

    # 8. Clean up mock data
    users_collection.delete_many({"email": dealer_email})
    print("========== ALL B2B DEALER ADDRESS INTEGRATION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_dealer_address_tests()
