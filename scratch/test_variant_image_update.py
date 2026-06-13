import io
import sys
from fastapi.testclient import TestClient
from app.main import app
from app import auth
from app.database import users_collection, product_variants_collection, product_submodels_collection

def run_variant_image_update_test():
    print("========== STARTING B2B PRODUCT VARIANT IMAGE UPDATE INTEGRATION TEST ==========")
    client = TestClient(app)

    variant_id = "PVAR-IMG-TEST"
    submodel_id = "PSMD-IMG-TEST"
    admin_email = "admin_img_test@example.com"

    # 1. Clean up
    users_collection.delete_many({"email": admin_email})
    product_variants_collection.delete_many({"variant_id": variant_id})
    product_submodels_collection.delete_many({"submodel_id": submodel_id})

    # 2. Setup Super Admin
    users_collection.insert_one({
        "user_id": "EMP-IMG-ADMIN",
        "first_name": "Img",
        "last_name": "Admin",
        "email": admin_email,
        "role": "Super Admin",
        "status": "Active",
        "password_hash": auth.get_password_hash("123")
    })

    admin_token = auth.create_access_token({"sub": admin_email, "role": "Super Admin"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 3. Setup Variant and Submodel parent
    product_submodels_collection.insert_one({
        "submodel_id": submodel_id,
        "name": "Mock Submodel",
        "model_id": "PMOD-MOCK",
        "is_active": True
    })

    product_variants_collection.insert_one({
        "variant_id": variant_id,
        "sku_no": "SKU-IMG-TEST",
        "submodel_id": submodel_id,
        "product_images": [],
        "is_active": True
    })

    # 4. Perform PUT variant update with multiple images using multipart form
    print("Performing PUT update with multiple image files...")
    
    # Create two dummy in-memory files
    file1 = io.BytesIO(b"dummy image 1 data")
    file2 = io.BytesIO(b"dummy image 2 data")
    
    files = [
        ("images", ("image1.png", file1, "image/png")),
        ("images", ("image2.png", file2, "image/png"))
    ]
    
    data = {
        "is_active": "true",
        "mrp": "4500",
        "size": "58"
    }

    # We do a PUT request using the multi-file data
    resp = client.put(
        f"/api/v1/product-master/variants/{variant_id}",
        data=data,
        files=files,
        headers=admin_headers
    )
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    result = resp.json()
    
    # 5. Verify images were correctly saved
    print("Verifying variant image updates in MongoDB...")
    db_variant = product_variants_collection.find_one({"variant_id": variant_id})
    assert db_variant is not None
    assert len(db_variant["product_images"]) == 2
    assert db_variant["product_images"][0].startswith(f"/qrcodes/Variants/{variant_id}/image_0")
    assert db_variant["product_images"][1].startswith(f"/qrcodes/Variants/{variant_id}/image_1")
    print("✅ Verified 2 product images were successfully uploaded and saved!")

    # 6. Cleanup
    users_collection.delete_many({"email": admin_email})
    product_variants_collection.delete_many({"variant_id": variant_id})
    product_submodels_collection.delete_many({"submodel_id": submodel_id})
    print("========== ALL VARIANT IMAGE UPDATE TESTS PASSED SUCCESSFULLY! ==========")

if __name__ == "__main__":
    run_variant_image_update_test()
