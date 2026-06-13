import asyncio
import sys
from fastapi import HTTPException
from app.api.user_api import UserOperations
from app import schemas
from app.database import users_collection
from app.admin import admin
from starlette.requests import Request

# Simple mock request with custom session
class MockRequest:
    def __init__(self, session_data=None):
        self.session = session_data or {}

async def test_department_inheritance():
    print("Testing Department Inheritance Logic...")
    
    # Clean up any leftover test users first
    users_collection.delete_many({"email": {"$regex": "^test_inherit_.*@example.com$"}})
    
    # ----------------------------------------------------
    # Part 1: Test user creation via API
    # ----------------------------------------------------
    print("\n1. Testing API User Creation with Department Inheritance...")
    
    # Case A: Creator has a custom department "QUALITY_CONTROL"
    creator_qc = {
        "user_id": "EMP26AAAA0001",
        "role": "Super Admin",
        "department": "QUALITY_CONTROL"
    }
    
    user_data_qc = schemas.UserCreate(
        email="test_inherit_api_qc@example.com",
        first_name="API QC",
        last_name="Tester",
        age=28,
        gender="Male",
        blood_group="A+",
        password="123",
        role="Scanner",
        employee_id="VEGA_TEST_QC",
        mobile_number="9999999001"
    )
    
    created_user_qc = UserOperations.create_user(user_data_qc, creator_qc)
    print(f"   Created API user: {created_user_qc['email']} | Dept: {created_user_qc['department']}")
    assert created_user_qc["department"] == "QUALITY_CONTROL", f"Expected department 'QUALITY_CONTROL', got '{created_user_qc['department']}'"
    
    # Case B: Creator has NO department field (should default to "PRODUCTION")
    creator_no_dept = {
        "user_id": "EMP26AAAA0001",
        "role": "Super Admin"
    }
    
    user_data_prod = schemas.UserCreate(
        email="test_inherit_api_prod@example.com",
        first_name="API Prod",
        last_name="Tester",
        age=32,
        gender="Female",
        blood_group="B-",
        password="123",
        role="Linker",
        employee_id="VEGA_TEST_PROD",
        mobile_number="9999999002"
    )
    
    created_user_prod = UserOperations.create_user(user_data_prod, creator_no_dept)
    print(f"   Created API user: {created_user_prod['email']} | Dept: {created_user_prod['department']}")
    assert created_user_prod["department"] == "PRODUCTION", f"Expected department 'PRODUCTION', got '{created_user_prod['department']}'"
    
    # ----------------------------------------------------
    # Part 2: Test user creation via Starlette-Admin view
    # ----------------------------------------------------
    print("\n2. Testing Starlette-Admin User Creation with Department Inheritance...")
    
    # Get the User view
    user_view = None
    for view in admin._views:
        if view.identity == "users":
            user_view = view
            break
            
    assert user_view is not None, "Could not find User view in admin"
    
    # Set up creator admin in DB with custom department
    creator_admin_id = "EMP_TEST_ADMIN_1"
    users_collection.delete_many({"user_id": creator_admin_id})
    users_collection.insert_one({
        "user_id": creator_admin_id,
        "first_name": "Test",
        "last_name": "Admin",
        "role": "Super Admin",
        "email": "test_admin_inherit@example.com",
        "mobile_number": "9999999003",
        "password": "hashed",
        "department": "DESIGN_AND_DEVELOPMENT",
        "age": 40,
        "gender": "Male",
        "blood_group": "O+"
    })
    
    # Case A: Admin with department "DESIGN_AND_DEVELOPMENT" in session
    mock_request_design = MockRequest({
        "admin_user": {
            "id": creator_admin_id,
            "name": "Test Admin",
            "role": "Super Admin",
            "email": "test_admin_inherit@example.com"
        }
    })
    
    form_data_design = {
        "email": "test_inherit_admin_design@example.com",
        "first_name": "Admin Design",
        "last_name": "Tester",
        "age": 25,
        "gender": "Female",
        "blood_group": "AB+",
        "role": "Inspector",
        "employee_id": "VEGA_TEST_DSN",
        "mobile_number": "9999999004",
        "status": "Active"
    }
    
    created_admin_user_dsn = await user_view.create(mock_request_design, form_data_design)
    print(f"   Created Admin user: {created_admin_user_dsn.email} | Dept: {created_admin_user_dsn.department}")
    assert created_admin_user_dsn.department == "DESIGN_AND_DEVELOPMENT", f"Expected department 'DESIGN_AND_DEVELOPMENT', got '{created_admin_user_dsn.department}'"
    
    # Case B: Admin in session has no department in database
    creator_admin_id_nodept = "EMP_TEST_ADMIN_2"
    users_collection.delete_many({"user_id": creator_admin_id_nodept})
    users_collection.insert_one({
        "user_id": creator_admin_id_nodept,
        "first_name": "Test",
        "last_name": "Admin2",
        "role": "Super Admin",
        "email": "test_admin_inherit2@example.com",
        "mobile_number": "9999999005",
        "password": "hashed",
        "age": 45,
        "gender": "Female",
        "blood_group": "A-"
        # No department field!
    })
    
    mock_request_nodept = MockRequest({
        "admin_user": {
            "id": creator_admin_id_nodept,
            "name": "Test Admin 2",
            "role": "Super Admin",
            "email": "test_admin_inherit2@example.com"
        }
    })
    
    form_data_nodept = {
        "email": "test_inherit_admin_nodept@example.com",
        "first_name": "Admin NoDept",
        "last_name": "Tester",
        "age": 30,
        "gender": "Male",
        "blood_group": "O-",
        "role": "Scanner",
        "employee_id": "VEGA_TEST_ND",
        "mobile_number": "9999999006",
        "status": "Active"
    }
    
    created_admin_user_nd = await user_view.create(mock_request_nodept, form_data_nodept)
    print(f"   Created Admin user: {created_admin_user_nd.email} | Dept: {created_admin_user_nd.department}")
    assert created_admin_user_nd.department == "PRODUCTION", f"Expected default department 'PRODUCTION', got '{created_admin_user_nd.department}'"
    
    # ----------------------------------------------------
    # Cleanup
    # ----------------------------------------------------
    print("\nCleaning up test records from database...")
    users_collection.delete_many({"email": {"$regex": "^test_inherit_.*@example.com$"}})
    users_collection.delete_many({"user_id": {"$in": [creator_admin_id, creator_admin_id_nodept]}})
    print("Cleanup completed successfully.")
    
    print("\n✓ SUCCESS: All department inheritance test cases passed flawlessly!")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(test_department_inheritance())
