import sys
import os
from datetime import datetime

# Setup path so we can import from app
sys.path.append("/Users/hawk/Downloads/vega_traceability_backend")

from app.database import b2b_gst_settings_collection
from app import schemas
from app.api.b2b_admin_api import B2BGstSettingsOperations

# Clean any existing test documents
b2b_gst_settings_collection.delete_many({"state": {"$in": ["Ontario Test", "Alberta Test"]}})

print("--- Starting GST Settings API unit test ---")

# Mock Admin User
admin_user = {"user_id": "SYS-ADMIN-01", "role": "Super Admin"}

# 1. Create a GST Setting
create_data = schemas.B2BGstSettingCreate(
    state="Ontario Test",
    tax_type="HST",
    percent=13.0
)

created = B2BGstSettingsOperations.create_setting(create_data, admin_user)
print("1. Created GST Setting successfully:")
print(created)

assert created["state"] == "Ontario Test"
assert created["tax_type"] == "HST"
assert created["percent"] == 13.0
assert "setting_id" in created

# 2. Prevent Duplicate State
try:
    duplicate_data = schemas.B2BGstSettingCreate(
        state="ontario test", # Case insensitive check
        tax_type="HST",
        percent=13.0
    )

    B2BGstSettingsOperations.create_setting(duplicate_data, admin_user)
    print("Error: Duplicate state check failed!")
    sys.exit(1)
except Exception as e:
    print("2. Correctly prevented duplicate state creation:", str(e))

# 3. Get All Settings
settings = B2BGstSettingsOperations.get_settings()
print(f"3. Retrieved {len(settings)} GST Settings.")
assert len(settings) >= 1

# 4. Get Specific Setting
setting_id = created["setting_id"]
fetched = B2BGstSettingsOperations.get_setting(setting_id)
print("4. Fetched specific setting successfully:")
print(fetched)
assert fetched["state"] == "Ontario Test"

# 5. Update Setting
update_data = schemas.B2BGstSettingUpdate(
    percent=14.0,
    tax_type="HST New"
)
updated = B2BGstSettingsOperations.update_setting(setting_id, update_data)
print("5. Updated setting successfully:")
print(updated)
assert updated["percent"] == 14.0
assert updated["tax_type"] == "HST New"

# 6. Delete Setting
deleted = B2BGstSettingsOperations.delete_setting(setting_id)
print("6. Deleted setting successfully:")
print(deleted)

# Clean up
b2b_gst_settings_collection.delete_many({"state": {"$in": ["Ontario Test", "Alberta Test"]}})
print("\n--- All tests passed successfully! ---")
