import os
import certifi
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

def get_current_time():
    IST = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(IST).replace(tzinfo=None)

def generate_custom_id(prefix: str, collection, id_field: str) -> str:
    current_year = get_current_time().year
    yy = str(current_year)[-2:]
    count_this_year = collection.count_documents({id_field: {"$regex": f"^{prefix}{yy}"}})
    xx_index = count_this_year // 9999
    count = (count_this_year % 9999) + 1
    first_char = chr(65 + (xx_index // 26))
    second_char = chr(65 + (xx_index % 26))
    return f"{prefix}{yy}{first_char}{second_char}{count:04d}"

def seed_complete():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]

    brands_col = db["product_brands"]
    categories_col = db["product_categories"]
    subcategories_col = db["product_subcategories"]
    models_col = db["product_models"]
    submodels_col = db["product_submodels"]
    variants_col = db["product_variants"]

    # Clear current master data to reseed cleanly (optional)
    brands_col.delete_many({})
    categories_col.delete_many({})
    subcategories_col.delete_many({})
    models_col.delete_many({})
    submodels_col.delete_many({})
    variants_col.delete_many({})

    now = get_current_time()
    yy = str(now.year)[-2:]

    print("Seeding Categories...")
    category_id = f"PCAT{yy}AAAA0001"
    categories_col.insert_one({
        "category_id": category_id,
        "name": "Helmets",
        "is_active": True,
        "created_by": "SYSTEM",
        "created_at": now
    })
    print(f"✓ Category created: Helmets ({category_id})")

    print("Seeding Subcategories...")
    subcat1_id = f"PSUB{yy}AAAA0001"
    subcat2_id = f"PSUB{yy}AAAA0002"
    subcategories_col.insert_one({
        "subcategory_id": subcat1_id,
        "name": "Full Face Helmets",
        "category_id": category_id,
        "is_active": True,
        "created_by": "SYSTEM",
        "created_at": now
    })
    subcategories_col.insert_one({
        "subcategory_id": subcat2_id,
        "name": "Open Face Helmets",
        "category_id": category_id,
        "is_active": True,
        "created_by": "SYSTEM",
        "created_at": now
    })
    print(f"✓ Subcategories created: Full Face ({subcat1_id}), Open Face ({subcat2_id})")

    print("Seeding Brands...")
    brand_id = f"PBRD{yy}AAAA0001"
    brands_col.insert_one({
        "brand_id": brand_id,
        "name": "Vega",
        "description": "Premium Helmets & Accessories",
        "logo_url": "/qrcodes/Brands/PBRD26AAAA0001/logo.png",
        "is_active": True,
        "size_master": [
            ["xs", 600, category_id],
            ["s", 800, category_id],
            ["m", 1000, category_id],
            ["l", 1100, category_id],
            ["xl", 1200, category_id],
            ["xxl", 1400, category_id]
        ],
        "created_by": "SYSTEM",
        "created_at": now
    })
    print(f"✓ Brand created: Vega ({brand_id})")

    print("Seeding Models...")
    model1_id = f"PMOD{yy}AAAA0001"
    models_col.insert_one({
        "model_id": model1_id,
        "name": "CLASSIC XOR TRACKER",
        "brand_id": brand_id,
        "brand_name": "Vega",
        "brand_status": True,
        "brand_is_active": True,
        "category_id": category_id,
        "category_name": "Helmets",
        "category_status": True,
        "category_is_active": True,
        "subcategory_id": subcat1_id,
        "subcategory_name": "Full Face Helmets",
        "subcategory_status": True,
        "subcategory_is_active": True,
        "is_active": True,
        "created_by": "SYSTEM",
        "created_at": now
    })
    print(f"✓ Model created: CLASSIC XOR TRACKER ({model1_id})")

    print("Seeding Submodels...")
    submodel1_id = f"PSMD{yy}AAAA0001"
    submodels_col.insert_one({
        "submodel_id": submodel1_id,
        "name": "XOR MATTE RED/WHITE",
        "model_id": model1_id,
        "model_name": "CLASSIC XOR TRACKER",
        "model_status": True,
        "model_is_active": True,
        "image": "/qrcodes/Brands/PBRD26AAAA0001/logo.png",
        "is_active": True,
        "box_weight": 1.4,
        "box_dimension": "35x25x25",
        "carton_weight": 8.5,
        "carton_dimension": "72x52x52",
        "packaging_details": "6 units per carton, individual box packaging.",
        "box_and_carton_dimensions": "Box: 35x25x25, Carton: 72x52x52",
        "carton_numbers": "BOX-CAR-01",
        "created_by": "SYSTEM",
        "created_at": now
    })
    print(f"✓ Submodel created: XOR MATTE RED/WHITE ({submodel1_id})")

    print("Seeding Variants...")
    v1_id = f"PVAR{yy}AAAA0001"
    variants_col.insert_one({
        "variant_id": v1_id,
        "sku_no": "CLASSIC-XOR-RED-L",
        "submodel_id": submodel1_id,
        "gs1_barcode": "1234567890123",
        "short_description": "Retro classic design with maximum comfort.",
        "long_description": "Perfectly combines safety with style. High impact strength shell with retro decals.",
        "carton_box_size": 6,
        "carton_barcode": "1234567890999",
        "product_images": ["/qrcodes/Brands/PBRD26AAAA0001/logo.png"],
        "color": "Matte Red/White",
        "size_name": "L",
        "size": 1100,  # resolved from size master
        "finish": "Matte",
        "certification": ["DOT", "ECE", "ISI"],
        "visor_type": "Clear",
        "spoiler": "No",
        "chinstrap_lock": "Double D-Ring",
        "pinlock": "Yes",
        "mrp": {"INR": 4500.0},
        "is_active": True,
        "created_by": "SYSTEM",
        "created_at": now
    })
    print(f"✓ Variant created: CLASSIC-XOR-RED-L ({v1_id})")

    print("\n✅ Seed complete! All master data restored successfully.")

if __name__ == "__main__":
    seed_complete()
