import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.product_api import (
    ProductCategoryOperations,
    ProductSubCategoryOperations,
)
from app.schemas import (
    ProductCategoryCreate,
    ProductSubCategoryCreate,
)

def seed_custom_categories():
    print("=========================================")
    print("SEEDING CUSTOM CATEGORIES AND SUBCATEGORIES...")
    print("=========================================")

    admin_user = {"user_id": "seeder_02", "role": "Super Admin"}

    categories_to_create = [
        "Beanie Helmets",
        "Full Face Helmets",
        "3/4th Helmets",
        "Half Face Helmets",
        "Accessories",
        "Axor Helmets carbon helmet"
    ]

    for cat_name in categories_to_create:
        # Create Category
        cat = ProductCategoryOperations.create_category(
            ProductCategoryCreate(name=cat_name, is_active=True),
            current_user=admin_user
        )
        print(f"✓ Created Category: {cat['name']} ({cat['category_id']})")

        # Create 2 dummy subcategories for each
        subcat_names = [f"Premium {cat_name}", f"Standard {cat_name}"]
        for subcat_name in subcat_names:
            sub = ProductSubCategoryOperations.create_subcategory(
                ProductSubCategoryCreate(
                    name=subcat_name, 
                    category_id=cat["category_id"], 
                    is_active=True
                ),
                current_user=admin_user
            )
            print(f"  ↳ Created Subcategory: {sub['name']} ({sub['subcategory_id']})")

    print("\n=========================================")
    print("✓ SEEDING COMPLETED SUCCESSFULLY!")
    print("=========================================")

if __name__ == "__main__":
    seed_custom_categories()
