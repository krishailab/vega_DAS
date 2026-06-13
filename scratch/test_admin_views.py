import sys
import os

# Add path so python can find app
os.environ["PYTHONPATH"] = "."

try:
    print("Testing Starlette-Admin view registration...")
    from app.admin import admin
    
    # Check registered views
    registered_identities = [view.identity for view in admin._views]
    print("Registered View Identities:")
    for identity in registered_identities:
        print(f"  - {identity}")
        
    assert "dealer_signup_requests" in registered_identities, "dealer_signup_requests view is NOT registered!"
    print("✓ SUCCESS: dealer_signup_requests view is successfully registered in Starlette-Admin!")
    
    sys.exit(0)
except Exception as e:
    print("FAILED: View registration verification failed with an error:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
