import sys
import os
from fastapi import HTTPException

# Add path so python can find app
os.environ["PYTHONPATH"] = "."

try:
    from app.api.dealer_signup_api import DealerSignupOperations
    from app import schemas
    from app.database import dealer_signup_requests_collection, users_collection

    print("Cleaning any existing test data...")
    dealer_signup_requests_collection.delete_many({"email": "test_dealer@example.com"})
    users_collection.delete_many({"email": "test_dealer@example.com"})

    print("1. Testing Dealer Signup Submission (POST)...")
    mock_request_create = schemas.DealerSignupRequestCreate(
        business_name="Test Dealer Ltd",
        contact_name="John Doe",
        email="test_dealer@example.com",
        mobile_number="9998887770",
        alternate_mobile_number="9998887771",
        address="123 Motor Street",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        comments="Excited to join the network!"
    )

    created_req = DealerSignupOperations.create_request(mock_request_create)
    request_id = created_req["request_id"]
    print(f"✓ SUCCESS: Dealer request created with ID: {request_id}")
    assert created_req["status"] == "Pending"
    assert created_req["business_name"] == "Test Dealer Ltd"
    assert created_req["processed_by"] is None
    assert "created_at" in created_req
    assert "updated_at" in created_req

    print("\n2. Testing Duplicate Pending Request Protection...")
    try:
        DealerSignupOperations.create_request(mock_request_create)
        print("FAILED: Allowed duplicate pending signup request.")
        sys.exit(1)
    except HTTPException as e:
        if e.status_code == 400 and "already exists" in e.detail:
            print("✓ SUCCESS: Correctly rejected duplicate pending request!")
        else:
            print(f"FAILED: Duplicate test rejected with unexpected error: status_code={e.status_code}, detail={e.detail}")
            sys.exit(1)

    print("\n3. Testing Get Request Details (GET by ID)...")
    fetched_req = DealerSignupOperations.get_request(request_id)
    assert fetched_req["request_id"] == request_id
    assert fetched_req["contact_name"] == "John Doe"
    print("✓ SUCCESS: Fetched correct request details.")

    print("\n4. Testing List Requests (GET all)...")
    requests_list = DealerSignupOperations.get_requests()
    assert len(requests_list) >= 1
    assert any(r["request_id"] == request_id for r in requests_list)
    print(f"✓ SUCCESS: Listed {len(requests_list)} requests, including ours.")

    print("\n5. Testing List Requests with Status Filter...")
    pending_list = DealerSignupOperations.get_requests(status_filter="Pending")
    assert len(pending_list) >= 1
    assert all(r["status"] == "Pending" for r in pending_list)
    approved_list = DealerSignupOperations.get_requests(status_filter="Approved")
    assert all(r["status"] == "Approved" for r in approved_list)
    print("✓ SUCCESS: Status filtering works perfectly.")

    print("\n7. Testing Successful Rejection...")
    current_admin = {"user_id": "EMP26AAAA0001", "role": "Super Admin"}
    mock_update_reject_success = schemas.DealerSignupRequestUpdateStatus(
        approve=False
    )
    rejected_req = DealerSignupOperations.update_status(request_id, mock_update_reject_success, current_admin)
    assert rejected_req["status"] == "Rejected"
    assert rejected_req["processed_by"] == "EMP26AAAA0001"
    print("✓ SUCCESS: Request successfully rejected with appropriate audit fields.")

    print("\n8. Testing Approval Without Password (should fail)...")
    try:
        mock_update_approve_fail = schemas.DealerSignupRequestUpdateStatus(
            approve=True
        )
        DealerSignupOperations.update_status(request_id, mock_update_approve_fail, current_admin)
        print("FAILED: Allowed approval without password.")
        sys.exit(1)
    except HTTPException as e:
        if e.status_code == 400 and "password is required" in e.detail.lower():
            print("✓ SUCCESS: Correctly rejected approval without password!")
        else:
            print(f"FAILED: Approval without password rejected with unexpected error: status_code={e.status_code}, detail={e.detail}")
            sys.exit(1)

    print("\n9. Testing Successful Approval With Password...")
    mock_update_approve_success = schemas.DealerSignupRequestUpdateStatus(
        approve=True,
        password="dealerpassword123"
    )
    approved_req = DealerSignupOperations.update_status(request_id, mock_update_approve_success, current_admin)
    assert approved_req["status"] == "Approved"
    assert approved_req["processed_by"] == "EMP26AAAA0001"
    print("✓ SUCCESS: Request successfully approved status transitioned to Approved.")

    print("\n10. Verifying Created Dealer User in Database...")
    dealer_user = users_collection.find_one({"email": "test_dealer@example.com"})
    assert dealer_user is not None, "Dealer user was not created in the database!"
    assert dealer_user["role"] == "Dealer"
    assert dealer_user["first_name"] == "John Doe"
    assert dealer_user["mobile_number"] == "9998887770"
    assert dealer_user["status"] == "Active"
    
    # Verify nested company address
    addr = dealer_user["company_address"]
    assert addr is not None
    assert addr.get("address_id") is not None
    assert addr["address_id"].startswith("ADDR-")
    assert addr["business_name"] == "Test Dealer Ltd"
    assert addr["address_line"] == "123 Motor Street"
    assert addr["city"] == "Mumbai"
    assert addr["state"] == "Maharashtra"
    assert addr["pincode"] == "400001"
    assert addr["alternate_mobile"] == "9998887771"

    # Verify company_addresses list
    addresses = dealer_user.get("company_addresses")
    assert addresses is not None
    assert isinstance(addresses, list)
    assert len(addresses) == 1
    assert addresses[0]["address_id"] == addr["address_id"]
    assert addresses[0]["business_name"] == "Test Dealer Ltd"
    
    # Verify password authentication works with bcrypt
    from app import auth
    assert auth.verify_password("dealerpassword123", dealer_user["password"])
    print("✓ SUCCESS: Automatically created dealer user has correct fields, nested company address (with generated ID), company_addresses list, and hashed credentials!")

    print("\nCleaning up test data...")
    dealer_signup_requests_collection.delete_many({"email": "test_dealer@example.com"})
    users_collection.delete_many({"email": "test_dealer@example.com"})

    print("\nAll Dealer Signup API validation and operations checks passed flawlessly!")
    sys.exit(0)

except Exception as e:
    print("FAILED: Script failed with unexpected error:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
