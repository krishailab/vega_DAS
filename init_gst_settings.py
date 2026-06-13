import sys
import os
from datetime import datetime

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import b2b_gst_settings_collection
from app import schemas
from app.api.b2b_admin_api import B2BGstSettingsOperations

def init_gst_settings():
    print("Clearing existing B2B GST settings...")
    b2b_gst_settings_collection.delete_many({})

    # Mock admin user for audit fields
    admin_user = {"user_id": "SYSTEM", "role": "Super Admin"}

    # GST Settings from the Canadian Sales Tax tables
    tax_data = [
        {"state": "AB", "tax_type": "GST", "percent": 5.0},
        {"state": "BC", "tax_type": "GST + PST", "percent": 12.0},
        {"state": "MB", "tax_type": "GST + RST", "percent": 12.0},
        {"state": "NB", "tax_type": "HST", "percent": 15.0},
        {"state": "NL", "tax_type": "HST", "percent": 15.0},
        {"state": "NS", "tax_type": "HST", "percent": 14.0},
        {"state": "NT", "tax_type": "GST", "percent": 5.0},
        {"state": "NU", "tax_type": "GST", "percent": 5.0},
        {"state": "ON", "tax_type": "HST", "percent": 13.0},
        {"state": "PE", "tax_type": "HST", "percent": 15.0},
        {"state": "QC", "tax_type": "GST + QST", "percent": 14.98},
        {"state": "SK", "tax_type": "GST + PST", "percent": 11.0},
        {"state": "YT", "tax_type": "GST", "percent": 5.0}
    ]

    print("Adding provincial GST settings...")
    for item in tax_data:
        create_schema = schemas.B2BGstSettingCreate(
            state=item["state"],
            tax_type=item["tax_type"],
            percent=item["percent"]
        )
        created = B2BGstSettingsOperations.create_setting(create_schema, admin_user)
        print(f"✓ Created: {created['state']} | {created['tax_type']} | {created['percent']}% (ID: {created['setting_id']})")

    print("\n✅ B2B GST Settings initialization complete!")

if __name__ == "__main__":
    init_gst_settings()
