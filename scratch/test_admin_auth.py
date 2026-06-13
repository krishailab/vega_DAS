import asyncio
import sys
from starlette.requests import Request
from starlette.responses import Response

# Mock request and response to simulate starlette-admin auth flow
class MockSession(dict):
    pass

class MockRequest:
    def __init__(self):
        self.session = MockSession()
        
    def url_for(self, name):
        return f"http://localhost:8000{name.replace(':', '/')}"

class MockResponse:
    pass

async def test_auth():
    print("Testing VegaAdminAuthProvider authentication flow...")
    try:
        from app.admin import admin
        from starlette_admin.exceptions import LoginFailed
        
        provider = admin.auth_provider
        if not provider:
            print("FAILED: No auth provider found on admin dashboard.")
            sys.exit(1)
            
        print("1. Testing unauthorized is_authenticated...")
        req = MockRequest()
        is_auth = await provider.is_authenticated(req)
        if is_auth:
            print("   FAILED: Unauthenticated request returned True.")
            sys.exit(1)
        print("   Success! Unauthenticated request returned False.")
        
        print("2. Testing login with invalid user...")
        try:
            await provider.login("invalid_user@vega.com", "wrong_password", False, req, MockResponse())
            print("   FAILED: Invalid login did not raise LoginFailed.")
            sys.exit(1)
        except LoginFailed as e:
            print(f"   Success! Caught expected LoginFailed: {e.msg}")
            
        print("3. Testing login with non-admin role user...")
        # Sahana has Inspector role (not Super/Master Admin)
        try:
            # Note: Sahana has email or mobile but we'll try to check if she raises privileges error
            await provider.login("Arjun@vega.com", "123", False, req, MockResponse())
            print("   FAILED: Scanner role login did not raise privilege exception.")
            sys.exit(1)
        except LoginFailed as e:
            print(f"   Success! Caught expected non-admin error: {e.msg}")
            
        print("4. Testing login with valid Super Admin user...")
        # Super admin is Karan@vega.com with password '123'
        resp = await provider.login("Karan@vega.com", "123", False, req, MockResponse())
        if "admin_user" in req.session:
            admin_data = req.session["admin_user"]
            print(f"   Success! Logged in as: {admin_data['name']} ({admin_data['role']})")
        else:
            print("   FAILED: Session did not store admin_user.")
            sys.exit(1)
            
        print("5. Testing is_authenticated after valid login...")
        is_auth = await provider.is_authenticated(req)
        if not is_auth:
            print("   FAILED: Authenticated request returned False.")
            sys.exit(1)
        print("   Success! Authenticated request returned True.")
        
        print("6. Testing get_admin_user details...")
        admin_user = await provider.get_admin_user(req)
        if admin_user and admin_user.username == admin_data["name"]:
            print(f"   Success! AdminUser returned correct username: {admin_user.username}")
        else:
            print("   FAILED: AdminUser details mismatch or None.")
            sys.exit(1)
            
        print("7. Testing logout...")
        await provider.logout(req)
        if "admin_user" in req.session or await provider.is_authenticated(req):
            print("   FAILED: Session not cleared after logout.")
            sys.exit(1)
        print("   Success! Session cleared and unauthenticated after logout.")
        
        print("\nAll authentication test cases passed successfully!")
        sys.exit(0)
    except Exception as e:
        print("FAILED: Auth flow test failed with an error:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_auth())
