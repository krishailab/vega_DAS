import sys
import os
from fastapi import HTTPException
from starlette.requests import Request
from starlette_admin.exceptions import FormValidationError

# Ensure PYTHONPATH contains current directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, users_collection, plants_collection
from app import schemas, utils
from app.api.user_api import UserOperations
from app.api.plant_api import PlantOperations
from app.admin import admin, PyMongoModelView, MongoDocument

# Mock Starlette-Admin request with custom session
class MockSession(dict):
    pass

class MockRequest:
    def __init__(self, user_id=None, role=None, department="PRODUCTION"):
        self.session = MockSession()
        if user_id:
            self.session["admin_user"] = {
                "id": user_id,
                "name": "Test Admin",
                "role": role,
                "email": "testadmin@vega.com"
            }

async def run_tests():
    print("=========================================")
    print("RUNNING PLANT & ASSIGNMENT VERIFICATION  ")
    print("=========================================")

    # Clear previous test data to avoid pollution
    users_collection.delete_many({"email": {"$regex": "@testplant.com$"}})
    plants_collection.delete_many({"plant_name": {"$regex": "^Test Plant"}})

    creator_super = {"user_id": "EMP26AAAA0001", "role": "Super Admin"}
    creator_master = {"user_id": "EMP26AAAA0002", "role": "Master Admin", "department": "SHELL"}

    # -------------------------------------------------------------
    # 1. PLANT CRUD OPERATIONS TEST
    # -------------------------------------------------------------
    print("\n1. Testing Plant CRUD endpoints via PlantOperations...")
    
    plant_create_data = schemas.PlantCreate(
        plant_name="Test Plant 1",
        plant_address="123 Industrial Area, Sector 5, Bengaluru"
    )
    
    created_plant = PlantOperations.create_plant(plant_create_data)
    plant_id = created_plant["plant_id"]
    print(f"✓ Plant created successfully with ID: {plant_id}")
    assert plant_id.startswith("PLT"), "Plant ID must start with PLT"
    assert created_plant["plant_name"] == "Test Plant 1"
    assert created_plant["plant_address"] == "123 Industrial Area, Sector 5, Bengaluru"

    # Get plants
    all_plants = PlantOperations.get_plants()
    assert any(p["plant_id"] == plant_id for p in all_plants), "Created plant must be in the list"
    print("✓ Successfully listed all plants")

    # Update plant
    plant_update_data = schemas.PlantUpdate(
        plant_name="Test Plant 1 - Updated",
        plant_address="456 New Road, Sector 6, Bengaluru"
    )
    updated_plant = PlantOperations.update_plant(plant_id, plant_update_data)
    print("✓ Plant updated successfully")
    assert updated_plant["plant_name"] == "Test Plant 1 - Updated"
    assert updated_plant["plant_address"] == "456 New Road, Sector 6, Bengaluru"

    # -------------------------------------------------------------
    # 2. USER REGISTRATION PLANT VALIDATION TEST
    # -------------------------------------------------------------
    print("\n2. Testing User creation plant requirements...")
    
    # 2.1 Non-Super Admin without plant_id -> should fail
    master_create_no_plant = schemas.UserCreate(
        email="master_no_plant@testplant.com",
        first_name="Master",
        last_name="NoPlant",
        age=35,
        gender="M",
        blood_group="O+",
        password="123",
        role="Master Admin",
        employee_id="VEGA_9991",
        mobile_number="9999999991",
        part_id="PTR26AAAA0001" # Mock or exist part
    )
    
    try:
        UserOperations.create_user(master_create_no_plant, creator_super)
        print("❌ FAILED: Created non-Super Admin without a plant_id")
        sys.exit(1)
    except HTTPException as e:
        assert e.status_code == 400
        assert "Plant ID is required" in e.detail
        print("✓ SUCCESS: Correctly blocked user creation without plant_id")

    # 2.2 Non-Super Admin with invalid plant_id -> should fail
    master_create_invalid_plant = schemas.UserCreate(
        email="master_invalid_plant@testplant.com",
        first_name="Master",
        last_name="InvalidPlant",
        age=35,
        gender="M",
        blood_group="O+",
        password="123",
        role="Master Admin",
        employee_id="VEGA_9992",
        mobile_number="9999999992",
        part_id="PTR26AAAA0001",
        plant_id="PLT99999"
    )
    
    try:
        UserOperations.create_user(master_create_invalid_plant, creator_super)
        print("❌ FAILED: Created user with non-existent plant_id")
        sys.exit(1)
    except HTTPException as e:
        assert e.status_code == 400
        assert "does not exist" in e.detail
        print("✓ SUCCESS: Correctly blocked user creation with invalid plant_id")

    # 2.3 Non-Super Admin with valid plant_id -> should succeed and enrich plant name & address
    master_create_valid_plant = schemas.UserCreate(
        email="master_valid_plant@testplant.com",
        first_name="Master",
        last_name="ValidPlant",
        age=35,
        gender="M",
        blood_group="O+",
        password="123",
        role="Master Admin",
        employee_id="VEGA_9993",
        mobile_number="9999999993",
        part_id="PTR26AAAA0001",
        plant_id=plant_id
    )
    
    created_user = UserOperations.create_user(master_create_valid_plant, creator_super)
    created_user_id = created_user["user_id"]
    print(f"✓ User created successfully with valid plant. ID: {created_user_id}")
    assert created_user["plant_id"] == plant_id
    assert created_user["plant_name"] == "Test Plant 1 - Updated"
    assert created_user["plant_address"] == "456 New Road, Sector 6, Bengaluru"
    print("✓ SUCCESS: Verified user document has correctly resolved denormalized plant name and address!")

    # -------------------------------------------------------------
    # 3. USER UPDATE PLANT VALIDATION TEST
    # -------------------------------------------------------------
    print("\n3. Testing User updates and plant field validations...")

    # 3.1 Non-Super Admin trying to clear plant_id -> should fail
    update_clear_plant = schemas.UserUpdate(plant_id="")
    try:
        UserOperations.update_user(created_user_id, update_clear_plant, creator_super)
        print("❌ FAILED: Allowed non-Super Admin to clear their plant_id")
        sys.exit(1)
    except HTTPException as e:
        assert e.status_code == 400
        assert "Plant ID is required" in e.detail
        print("✓ SUCCESS: Correctly blocked clearing plant_id on non-Super Admin")

    # 3.2 Non-Super Admin updating to another valid plant -> should succeed and sync updated fields
    plant_2_data = schemas.PlantCreate(
        plant_name="Test Plant 2",
        plant_address="789 Secondary Road, Sector 7, Chennai"
    )
    plant_2 = PlantOperations.create_plant(plant_2_data)
    plant_2_id = plant_2["plant_id"]
    
    update_valid_plant = schemas.UserUpdate(plant_id=plant_2_id)
    updated_user = UserOperations.update_user(created_user_id, update_valid_plant, creator_super)
    assert updated_user["plant_id"] == plant_2_id
    assert updated_user["plant_name"] == "Test Plant 2"
    assert updated_user["plant_address"] == "789 Secondary Road, Sector 7, Chennai"
    print("✓ SUCCESS: Correctly validated and updated plant details on user record")

    # 3.3 Dynamic update propagation: when a plant's name/address changes, users assigned to it must be updated
    plant_2_update = schemas.PlantUpdate(
        plant_name="Test Plant 2 - Brand New Name",
        plant_address="789 Brand New Road, Sector 7, Chennai"
    )
    PlantOperations.update_plant(plant_2_id, plant_2_update)
    
    user_record = users_collection.find_one({"user_id": created_user_id})
    assert user_record["plant_name"] == "Test Plant 2 - Brand New Name"
    assert user_record["plant_address"] == "789 Brand New Road, Sector 7, Chennai"
    print("✓ SUCCESS: Verified plant detail updates dynamically synced to all assigned users!")

    # -------------------------------------------------------------
    # 4. PLANT DELETION REFERENTIAL INTEGRITY TEST
    # -------------------------------------------------------------
    print("\n4. Testing Plant deletion referential integrity...")
    
    # 4.1 Deleting a plant with active user assignments -> should fail
    try:
        PlantOperations.delete_plant(plant_2_id)
        print("❌ FAILED: Allowed deleting a plant with active user assignments")
        sys.exit(1)
    except HTTPException as e:
        assert e.status_code == 400
        assert "assigned to active users" in e.detail
        print("✓ SUCCESS: Correctly blocked deletion of plant with active user references")

    # 4.2 Deleting a plant with NO user assignments -> should succeed
    PlantOperations.delete_plant(plant_id)
    assert plants_collection.find_one({"plant_id": plant_id}) is None
    print("✓ SUCCESS: Correctly allowed deletion of unassigned plant")

    # -------------------------------------------------------------
    # 5. STARLETTE-ADMIN VIEWS & LIFECYCLE TESTS
    # -------------------------------------------------------------
    print("\n5. Testing Starlette-Admin view and lifecycle hooks...")
    
    user_view = None
    plant_view = None
    for view in admin.views:
        if view.identity == "users":
            user_view = view
        elif view.identity == "plants":
            plant_view = view

    assert user_view is not None, "Users view not registered in Admin"
    assert plant_view is not None, "Plants view not registered in Admin"
    
    user_fields_list = user_view.fields
    user_fields = [f.name for f in user_fields_list]
    assert "plant_id" in user_fields, "plant_id must be exposed in User View"
    assert "plant_name" in user_fields, "plant_name must be exposed in User View"
    assert "plant_address" in user_fields, "plant_address must be exposed in User View"
    print("✓ SUCCESS: Exposed plant_id, plant_name, and plant_address in admin User fields list!")

    # Test Starlette-Admin custom ID generation hook for Plants
    request = MockRequest()
    plant_admin_data = {
        "plant_name": "Test Plant Admin Panel",
        "plant_address": "Admin Rd 1"
    }
    
    created_admin_plant_doc = await plant_view.create(request, plant_admin_data)
    admin_plant_id = created_admin_plant_doc.plant_id
    assert admin_plant_id.startswith("PLT"), "Admin panel should auto-generate sequential PLT IDs"
    print(f"✓ SUCCESS: Admin panel auto-generated sequential Plant ID: {admin_plant_id}")
    
    # Test Starlette-Admin validation: non-Super Admin must have a plant
    invalid_user_admin_data = {
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin_invalid@testplant.com",
        "role": "Master Admin",
        "mobile_number": "1234567890",
        "age": 30,
        "gender": "M",
        "blood_group": "A+",
        "status": "Active",
        "plant_id": "" # empty plant
    }
    
    try:
        await user_view.create(request, invalid_user_admin_data)
        print("❌ FAILED: Admin panel allowed creating non-Super Admin without plant")
        sys.exit(1)
    except FormValidationError as e:
        assert "plant_id" in e.errors
        print("✓ SUCCESS: Admin panel correctly raised FormValidationError for empty plant on Master Admin!")

    # Test Starlette-Admin validation: invalid plant ID
    invalid_plant_user_admin_data = {
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin_invalid_plt@testplant.com",
        "role": "Master Admin",
        "mobile_number": "1234567890",
        "age": 30,
        "gender": "M",
        "blood_group": "A+",
        "status": "Active",
        "plant_id": "PLT_INVALID_ID"
    }
    
    try:
        await user_view.create(request, invalid_plant_user_admin_data)
        print("❌ FAILED: Admin panel allowed user with invalid plant ID")
        sys.exit(1)
    except FormValidationError as e:
        assert "plant_id" in e.errors
        assert "does not exist" in e.errors["plant_id"]
        print("✓ SUCCESS: Admin panel correctly blocked creation of user with invalid plant ID!")

    # Test Starlette-Admin: valid plant ID on non-Super Admin
    valid_user_admin_data = {
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin_valid_plt@testplant.com",
        "role": "Master Admin",
        "mobile_number": "1234567890",
        "age": 30,
        "gender": "M",
        "blood_group": "A+",
        "status": "Active",
        "plant_id": admin_plant_id
    }
    
    created_admin_user_doc = await user_view.create(request, valid_user_admin_data)
    assert created_admin_user_doc.plant_id == admin_plant_id
    assert created_admin_user_doc.plant_name == "Test Plant Admin Panel"
    assert created_admin_user_doc.plant_address == "Admin Rd 1"
    print("✓ SUCCESS: Admin panel successfully validated and enriched user with plant details!")

    # Clean up test data
    users_collection.delete_many({"email": {"$regex": "@testplant.com$"}})
    plants_collection.delete_many({"plant_name": {"$regex": "^Test Plant"}})
    
    print("\n=========================================")
    print("✓ ALL PLANT & ASSIGNMENT TESTS PASSED!   ")
    print("=========================================")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_tests())
