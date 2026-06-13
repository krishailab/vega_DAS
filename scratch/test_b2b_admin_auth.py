import sys
import os

# Add paths so Python can import the local app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.database import dealer_signup_requests_collection, users_collection

def run_integration_tests():
    print("========== RUNNING B2B ADMIN AUTH & FLEXIBLE SIGNUP STATUS VERIFICATION ==========")
    
    # 1. Initialize TestClient
    client = TestClient(app)
    
    # 2. Login as B2B Admin
    print("\n[Step 1] Authenticating as B2B Admin...")
    login_payload = {
        "username": "b2badmin@vega.com",
        "password": "123"
    }
    
    # login expects form-data
    response = client.post("/api/auth/login", data=login_payload)
    if response.status_code != 200:
        print(f"❌ FAILED: Unable to authenticate as B2B Admin. Status: {response.status_code}, Response: {response.text}")
        sys.exit(1)
        
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        print("❌ FAILED: Login response did not contain access_token.")
        sys.exit(1)
        
    print(f"✓ Success: Authenticated! Token type: {token_data.get('token_type')}")
    
    # Configure headers with Authorization token
    auth_headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # 3. Access Verification Checks
    print("\n[Step 2] Performing administrative access verification checks...")

    # Kiosk Config
    print("Checking Kiosk Config GET /api/v1/kiosk/ ...")
    res_kiosk = client.get("/api/v1/kiosk/", headers=auth_headers)
    assert res_kiosk.status_code == 200, f"Expected 200, got {res_kiosk.status_code}: {res_kiosk.text}"
    print("✓ Success: Kiosk config accessible!")

    # Users List
    print("Checking Users List GET /users/ ...")
    res_users = client.get("/users/", headers=auth_headers)
    assert res_users.status_code == 200, f"Expected 200, got {res_users.status_code}: {res_users.text}"
    print("✓ Success: Users management list accessible!")

    # Product categories
    print("Checking Products GET /api/v1/product-master/categories/ ...")
    res_prod_cats = client.get("/api/v1/product-master/categories/", headers=auth_headers)
    assert res_prod_cats.status_code == 200, f"Expected 200, got {res_prod_cats.status_code}: {res_prod_cats.text}"
    print("✓ Success: Product master catalog accessible!")

    # Asset categories
    print("Checking Assets GET /assets/categories ...")
    res_asset_cats = client.get("/assets/categories", headers=auth_headers)
    assert res_asset_cats.status_code == 200, f"Expected 200, got {res_asset_cats.status_code}: {res_asset_cats.text}"
    print("✓ Success: Asset categories accessible!")

    # Asset Dashboard
    print("Checking Assets GET /assets/dashboard ...")
    res_asset_dash = client.get("/assets/dashboard", headers=auth_headers)
    assert res_asset_dash.status_code == 200, f"Expected 200, got {res_asset_dash.status_code}: {res_asset_dash.text}"
    print("✓ Success: Asset dashboard accessible!")

    # 4. Flexible Dealer Status Coercion Check
    print("\n[Step 3] Verifying flexible dealer status coercion formats (bool vs string)...")

    # Clean existing test data first
    dealer_signup_requests_collection.delete_many({"email": {"$in": ["dealer_test_bool@example.com", "dealer_test_str@example.com", "dealer_test_str3@example.com"]}})
    users_collection.delete_many({"email": {"$in": ["dealer_test_bool@example.com", "dealer_test_str@example.com", "dealer_test_str3@example.com"]}})

    # Create Request 1 (to be approved using boolean true)
    req1_payload = {
        "business_name": "Test Dealer Bool Ltd",
        "contact_name": "John Bool",
        "email": "dealer_test_bool@example.com",
        "mobile_number": "9998881111",
        "alternate_mobile_number": "9998881112",
        "address": "101 Boolean Road",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001",
        "comments": "Testing true bool status input."
    }
    print("Submitting dealer signup request 1 (for boolean test)...")
    res_req1 = client.post("/dealer-signups/", json=req1_payload)
    assert res_req1.status_code == 201, f"Expected 201, got {res_req1.status_code}: {res_req1.text}"
    req1_id = res_req1.json()["request_id"]
    print(f"✓ Success: Request 1 created with ID: {req1_id}")

    # Create Request 2 (to be rejected using string 'Rejected')
    req2_payload = {
        "business_name": "Test Dealer Str Ltd",
        "contact_name": "Jane String",
        "email": "dealer_test_str@example.com",
        "mobile_number": "9998882222",
        "alternate_mobile_number": "9998882223",
        "address": "202 String Street",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001",
        "comments": "Testing string status input."
    }
    print("Submitting dealer signup request 2 (for string test)...")
    res_req2 = client.post("/dealer-signups/", json=req2_payload)
    assert res_req2.status_code == 201, f"Expected 201, got {res_req2.status_code}: {res_req2.text}"
    req2_id = res_req2.json()["request_id"]
    print(f"✓ Success: Request 2 created with ID: {req2_id}")

    # A. Approve Request 1 using boolean payload: true
    print("Approving Request 1 using `approve = True`...")
    res_approve1 = client.put(f"/dealer-signups/{req1_id}/status", json={"approve": True, "password": "dealerpassword123"}, headers=auth_headers)
    assert res_approve1.status_code == 200, f"Expected 200, got {res_approve1.status_code}: {res_approve1.text}"
    updated_req1 = res_approve1.json()
    assert updated_req1["status"] == "Approved", f"Expected Approved, got: {updated_req1['status']}"
    print("✓ Success: Request 1 correctly approved using boolean True payload.")

    # B. Reject Request 2 using string payload: 'Rejected'
    print("Rejecting Request 2 using `approve = 'Rejected'`...")
    res_reject2 = client.put(f"/dealer-signups/{req2_id}/status", json={"approve": "Rejected"}, headers=auth_headers)
    assert res_reject2.status_code == 200, f"Expected 200, got {res_reject2.status_code}: {res_reject2.text}"
    updated_req2 = res_reject2.json()
    assert updated_req2["status"] == "Rejected", f"Expected Rejected, got: {updated_req2['status']}"
    print("✓ Success: Request 2 correctly rejected using string 'Rejected' payload.")

    # C. Additional string validation test: 'Approved', 'yes', '1' -> True
    # Create Request 3 to verify string Approved conversion
    dealer_signup_requests_collection.delete_many({"email": "dealer_test_str3@example.com"})
    users_collection.delete_many({"email": "dealer_test_str3@example.com"})
    req3_payload = req2_payload.copy()
    req3_payload["email"] = "dealer_test_str3@example.com"
    req3_payload["mobile_number"] = "9998883333"
    res_req3 = client.post("/dealer-signups/", json=req3_payload)
    req3_id = res_req3.json()["request_id"]

    print("Approving Request 3 using string `approve = 'Approved'`...")
    res_approve3 = client.put(f"/dealer-signups/{req3_id}/status", json={"approve": "Approved", "password": "dealerpassword123"}, headers=auth_headers)
    assert res_approve3.status_code == 200, f"Expected 200, got {res_approve3.status_code}: {res_approve3.text}"
    updated_req3 = res_approve3.json()
    assert updated_req3["status"] == "Approved", f"Expected Approved, got: {updated_req3['status']}"
    print("✓ Success: Request 3 correctly approved using string 'Approved' payload.")

    # Clean up test signups
    dealer_signup_requests_collection.delete_many({"email": {"$in": ["dealer_test_bool@example.com", "dealer_test_str@example.com", "dealer_test_str3@example.com"]}})
    users_collection.delete_many({"email": {"$in": ["dealer_test_bool@example.com", "dealer_test_str@example.com", "dealer_test_str3@example.com"]}})
    print("✓ Success: Cleaned up temporary integration test dealer signup and user records from database.")

    print("\n========== ALL INTEGRATION AND SECURITY VERIFICATION TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_integration_tests()
