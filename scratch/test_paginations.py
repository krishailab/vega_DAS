import json
from fastapi.testclient import TestClient
from app.main import app
from app import auth

# Mock user for bypassing auth
mock_user = {
    "user_id": "EMP26AAAA0001",
    "first_name": "Test",
    "last_name": "User",
    "email": "test@example.com",
    "role": "Super Admin",
}

# Override dependencies
app.dependency_overrides[auth.get_current_user] = lambda: mock_user
auth.RoleChecker.__call__ = lambda self, user=None: mock_user

client = TestClient(app)

endpoints = [
    ("/api/v1/product-master/categories/", {}),
    ("/api/v1/product-master/subcategories/", {}),
    ("/api/v1/product-master/brands/", {}),
    ("/api/v1/product-master/models/", {}),
    ("/api/v1/product-master/submodels/", {}),
    ("/api/v1/product-master/variants/", {}),
    ("/assets/categories", {}),
    ("/assets/subcategories", {}),
    ("/assets/", {}),
    ("/users/", {}),
    ("/api/v1/b2b-admin/dealers", {}),
    ("/api/v1/b2b-admin/coupons/", {}),
    ("/api/v1/b2b-admin/gst-settings/", {}),
    ("/dealer-signups/requests", {}),
    ("/jobcards/", {}),
    ("/jobcards/JC0001/qrs-detailed", {}),
    ("/scans/user-history/EMP26AAAA0001", {}),
    ("/scans/my-history", {}),
    ("/api/parts", {}),
    ("/stations/", {}),
    ("/api/process/", {}),
    ("/api/plants/", {}),
    ("/shifts/", {}),
    ("/api/v1/kiosk/", {}),
]

print("Starting endpoint validation tests...")
print("=" * 80)

for url, params in endpoints:
    try:
        response = client.get(url, params=params)
        print(f"URL: {url}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                preview = {k: (f"list of length {len(v)}" if isinstance(v, list) else v) for k, v in data.items()}
                print(f"Response (Standardised): {json.dumps(preview, indent=2)}")
            else:
                print(f"Response (Non-dict list representation): {str(data)[:150]}...")
        else:
            print(f"Error Response: {response.text[:200]}")
    except Exception as e:
        print(f"Failed to test {url}: {e}")
    print("-" * 80)
