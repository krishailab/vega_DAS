import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.product_api import (
    ProductBrandOperations,
    ProductModelOperations,
)
from app.database import (
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection
)
from app.schemas import (
    ProductBrandCreate,
    ProductModelCreate,
)

def seed_custom_models():
    print("=========================================")
    print("SEEDING CUSTOM MODELS...")
    print("=========================================")

    admin_user = {"user_id": "seeder_03", "role": "Super Admin"}

    # 1. Get or Create Brands: Classic and AXOR
    brands_to_create = ["Classic", "AXOR"]
    brands_data = {}

    for brand_name in brands_to_create:
        existing_brand = product_brands_collection.find_one({"name": brand_name})
        if existing_brand:
            brands_data[brand_name] = existing_brand
            print(f"✓ Found existing Brand: {brand_name} ({existing_brand['brand_id']})")
        else:
            new_brand = ProductBrandOperations.create_brand(
                name=brand_name,
                description=f"{brand_name} Brand",
                logo=None,
                is_active=True,
                current_user=admin_user
            )
            brands_data[brand_name] = new_brand
            print(f"✓ Created Brand: {brand_name} ({new_brand['brand_id']})")

    # 2. Fetch all categories and subcategories
    categories = list(product_categories_collection.find())
    subcategories = list(product_subcategories_collection.find())
    
    # 3. Create Models for each Brand -> Category -> Subcategory
    for brand_name, brand in brands_data.items():
        for cat in categories:
            # Find subcategories belonging to this category
            cat_subs = [s for s in subcategories if s["category_id"] == cat["category_id"]]
            
            for sub in cat_subs:
                model_name = f"{brand_name} {sub['name']} Model"
                
                # Create the model
                new_model = ProductModelOperations.create_model(
                    ProductModelCreate(
                        name=model_name,
                        brand_id=brand["brand_id"],
                        category_id=cat["category_id"],
                        subcategory_id=sub["subcategory_id"],
                        is_active=True
                    ),
                    current_user=admin_user
                )
                print(f"  ↳ Created Model: {new_model['name']} ({new_model['model_id']})")

    print("\n=========================================")
    print("✓ MODEL SEEDING COMPLETED SUCCESSFULLY!")
    print("=========================================")

if __name__ == "__main__":
    seed_custom_models()
