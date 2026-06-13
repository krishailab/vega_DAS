import sys
import os
import re

# Dynamically add project root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from app.database import users_collection
from app import utils

# Fetch all existing sub-users (Reader, Inspector, Linker)
subusers = list(users_collection.find({"role": {"$in": ["Reader", "Inspector", "Linker"]}}))
print(f"Found {len(subusers)} existing sub-users to migrate.")

updated_count = 0
for u in subusers:
    user_id = u.get("user_id")
    mobile = u.get("mobile_number") or ""
    emp_id = u.get("employee_id") or ""
    
    # Extract integer part (digits) of employee_id
    digits = "".join(re.findall(r'\d+', emp_id))
    if not digits:
        digits = "123" # Fallback if no digits found
        
    qr_data = f"{mobile};{digits}"
    
    # Use master_admin_id or fallback to "system" for directory
    creator_id = u.get("master_admin_id") or "system"
    
    try:
        # Generate QR code
        qr_path = utils.generate_qr_file(qr_data, creator_id, "User", user_id)
        
        # Update user document
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"qrcode": qr_path}}
        )
        updated_count += 1
        print(f"Generated QR code for {user_id} ({mobile}) -> {qr_path} [Data: {qr_data}]")
    except Exception as e:
        print(f"Error generating QR code for {user_id}: {e}")

print(f"Successfully processed and updated {updated_count} sub-users.")
