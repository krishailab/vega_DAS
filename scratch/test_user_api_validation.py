import asyncio
import sys
from fastapi import HTTPException

# Add path so python can find app
import os
os.environ["PYTHONPATH"] = "."

try:
    from app.api.user_api import UserOperations
    from app import schemas
    
    # 1. Test creating a Super Admin - should fail with 400
    print("Testing create_user with role='Super Admin'...")
    mock_super_admin_create = schemas.UserCreate(
        email="test_super@example.com",
        first_name="Test",
        last_name="Super",
        age=30,
        gender="Male",
        blood_group="O+",
        password="123",
        role="Super Admin",
        employee_id="EMP99999",
        mobile_number="9876543210"
    )
    
    current_user = {"user_id": "EMP26AAAA0001", "role": "Super Admin"}
    
    try:
        UserOperations.create_user(mock_super_admin_create, current_user)
        print("FAILED: Allowed creating a Super Admin via API")
        sys.exit(1)
    except HTTPException as e:
        if e.status_code == 400 and "Creation of Super Admin is not allowed" in e.detail:
            print("✓ SUCCESS: Correctly rejected creation of Super Admin via API with 400 Bad Request!")
        else:
            print(f"FAILED: Rejected but with unexpected error: status_code={e.status_code}, detail={e.detail}")
            sys.exit(1)

    # 2. Test updating a user role to 'Super Admin' - should fail with 400
    print("\nTesting update_user changing role to 'Super Admin'...")
    mock_user_update = schemas.UserUpdate(
        role="Super Admin"
    )
    
    try:
        # User being updated is EMP26AAAA0002 (Inspector)
        UserOperations.update_user("EMP26AAAA0002", mock_user_update, current_user)
        print("FAILED: Allowed updating a user to Super Admin via API")
        sys.exit(1)
    except HTTPException as e:
        if e.status_code == 400 and "Cannot change role to Super Admin" in e.detail:
            print("✓ SUCCESS: Correctly rejected changing role to Super Admin via API with 400 Bad Request!")
        else:
            print(f"FAILED: Rejected but with unexpected error: status_code={e.status_code}, detail={e.detail}")
            sys.exit(1)
            
    print("\nAll User API Validation checks passed perfectly!")
    sys.exit(0)

except Exception as e:
    print("FAILED: Script failed with unexpected error:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
