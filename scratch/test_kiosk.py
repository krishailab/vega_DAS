import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from app.database import kiosks_collection
from app.api.kiosk_api import KioskOperations, KioskCache
from app.schemas import KioskVerifyPinRequest

# Clean up any residual test data
kiosks_collection.delete_many({})
KioskCache.clear()

print("=========================================")
print("RUNNING MULTI-TENANT KIOSK LOGIC VERIFICATION")
print("=========================================")

admin_a = {"user_id": "master_admin_a", "role": "Master Admin"}
admin_b = {"user_id": "master_admin_b", "role": "Master Admin"}
super_admin = {"user_id": "super_admin_01", "role": "Super Admin"}

# 1. Test Master Admin A Creation
print("1. Testing Kiosk registration for Master Admin A...")
kiosk_a = KioskOperations.create_kiosk(
    device_id="KIOSK_A",
    kiosk_token="token_a",
    admin_pin="111111",
    primary_color="#111111",
    secondary_color="#222222",
    background_color="#333333",
    logo=None,
    splash_image=None,
    is_update_mandatory=True,
    apk_download_url="https://drive.google.com/uc?export=download&id=FILE_A",
    target_master_admin_id=None,
    current_user=admin_a
)
assert kiosk_a["device_id"] == "KIOSK_A"
assert kiosk_a["master_admin_id"] == "master_admin_a"
print("✓ Master Admin A created their kiosk successfully!")

# 2. Test Multi-creation block for Master Admin A
print("\n2. Testing singleton creation constraint for Master Admin A...")
try:
    KioskOperations.create_kiosk(
        device_id="KIOSK_A_DUPLICATE",
        kiosk_token="token_a2",
        admin_pin="222222",
        primary_color="#444444",
        secondary_color="#555555",
        background_color="#666666",
        logo=None,
        splash_image=None,
        is_update_mandatory=False,
        apk_download_url="https://drive.google.com/uc?export=download&id=FILE_A2",
        target_master_admin_id=None,
        current_user=admin_a
    )
    assert False, "Should raise HTTPException for duplicate creation"
except HTTPException as e:
    assert e.status_code == 400
    assert "already has a Kiosk configuration" in e.detail
    print("✓ Multiple configs correctly blocked for a single Master Admin!")

# 3. Test Master Admin B Access Controls (Forbidden actions)
print("\n3. Testing Master Admin B trying to modify Master Admin A's kiosk...")
try:
    KioskOperations.update_kiosk(
        device_id="KIOSK_A",
        kiosk_token=None,
        admin_pin=None,
        primary_color="#999999",
        secondary_color=None,
        background_color=None,
        logo=None,
        splash_image=None,
        is_update_mandatory=None,
        apk_download_url=None,
        current_user=admin_b
    )
    assert False, "Should raise HTTPException for unauthorized update"
except HTTPException as e:
    assert e.status_code == 403
    assert "You do not own this Kiosk" in e.detail
    print("✓ Master Admin B update access correctly forbidden!")

try:
    KioskOperations.delete_kiosk(device_id="KIOSK_A", current_user=admin_b)
    assert False, "Should raise HTTPException for unauthorized delete"
except HTTPException as e:
    assert e.status_code == 403
    assert "You do not own this Kiosk" in e.detail
    print("✓ Master Admin B delete access correctly forbidden!")

# 4. Test Super Admin Central Controls
print("\n4. Testing Super Admin centralized permissions...")

# Super Admin creates Kiosk for Master Admin B
kiosk_b = KioskOperations.create_kiosk(
    device_id="KIOSK_B",
    kiosk_token="token_b",
    admin_pin="222222",
    primary_color="#121212",
    secondary_color="#343434",
    background_color="#565656",
    logo=None,
    splash_image=None,
    is_update_mandatory=False,
    apk_download_url="https://drive.google.com/uc?export=download&id=FILE_B",
    target_master_admin_id="master_admin_b",
    current_user=super_admin
)
assert kiosk_b["device_id"] == "KIOSK_B"
assert kiosk_b["master_admin_id"] == "master_admin_b"
print("✓ Super Admin registered Kiosk config for Master Admin B successfully!")

# Super Admin reads all kiosks
all_kiosks = KioskOperations.get_kiosks(current_user=super_admin)
assert len(all_kiosks) == 2
print("✓ Super Admin listed all configurations successfully!")

# Super Admin updates Master Admin A's Kiosk Config
updated_a = KioskOperations.update_kiosk(
    device_id="KIOSK_A",
    kiosk_token=None,
    admin_pin=None,
    primary_color="#FF0000",
    secondary_color=None,
    background_color=None,
    logo=None,
    splash_image=None,
    is_update_mandatory=None,
    apk_download_url=None,
    current_user=super_admin
)
assert updated_a["theme"]["primary_color"] == "#FF0000"
print("✓ Super Admin updated Master Admin A's config successfully!")

# Super Admin deletes Master Admin A's Kiosk Config
KioskOperations.delete_kiosk(device_id="KIOSK_A", current_user=super_admin)
all_kiosks_after = KioskOperations.get_kiosks(current_user=super_admin)
assert len(all_kiosks_after) == 1
assert all_kiosks_after[0]["device_id"] == "KIOSK_B"
print("✓ Super Admin deleted Master Admin A's config successfully!")

# Clean up
kiosks_collection.delete_many({})
KioskCache.clear()
print("\n=========================================")
print("✓ ALL MULTI-TENANT LOGIC TESTS PASSED!")
print("=========================================")
