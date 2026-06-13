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

def seed_products():
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

    brand_id = "PBRD26AAAA0003"
    category_id = "PCAT26AAAA0001"
    subcat1_id = "PSUB26AAAA0001"
    subcat2_id = "PSUB26AAAA0002"

    print("Fetching referenced Brand, Category, and Subcategories...")
    brand = brands_col.find_one({"brand_id": brand_id})
    category = categories_col.find_one({"category_id": category_id})
    subcat1 = subcategories_col.find_one({"subcategory_id": subcat1_id})
    subcat2 = subcategories_col.find_one({"subcategory_id": subcat2_id})

    if not brand:
        print(f"❌ Error: Brand {brand_id} not found!")
        return
    if not category:
        print(f"❌ Error: Category {category_id} not found!")
        return
    if not subcat1 or not subcat2:
        print(f"❌ Error: Subcategories not found!")
        return

    now = get_current_time()

    # 1. Seed Models
    print("\nSeeding Product Models...")
    model1_name = "CLASSIC XOR TRACKER"
    model2_name = "CLASSIC VINTAGE FULL FACE"

    # Model 1
    m1 = models_col.find_one({"name": model1_name, "brand_id": brand_id})
    if not m1:
        model1_id = generate_custom_id("PMOD", models_col, "model_id")
        m1_doc = {
            "model_id": model1_id,
            "name": model1_name,
            "brand_id": brand_id,
            "brand_name": brand["name"],
            "brand_status": brand["is_active"],
            "brand_is_active": brand["is_active"],
            "category_id": category_id,
            "category_name": category["name"],
            "category_status": category["is_active"],
            "category_is_active": category["is_active"],
            "subcategory_id": subcat1_id,
            "subcategory_name": subcat1["name"],
            "subcategory_status": subcat1["is_active"],
            "subcategory_is_active": subcat1["is_active"],
            "is_active": True,
            "created_by": "EMP26AAAA0001",
            "created_at": now
        }
        models_col.insert_one(m1_doc)
        print(f"✓ Created Model: {model1_name} ({model1_id})")
        m1 = m1_doc
    else:
        print(f"✓ Model {model1_name} already exists.")

    # Model 2
    m2 = models_col.find_one({"name": model2_name, "brand_id": brand_id})
    if not m2:
        model2_id = generate_custom_id("PMOD", models_col, "model_id")
        m2_doc = {
            "model_id": model2_id,
            "name": model2_name,
            "brand_id": brand_id,
            "brand_name": brand["name"],
            "brand_status": brand["is_active"],
            "brand_is_active": brand["is_active"],
            "category_id": category_id,
            "category_name": category["name"],
            "category_status": category["is_active"],
            "category_is_active": category["is_active"],
            "subcategory_id": subcat2_id,
            "subcategory_name": subcat2["name"],
            "subcategory_status": subcat2["is_active"],
            "subcategory_is_active": subcat2["is_active"],
            "is_active": True,
            "created_by": "EMP26AAAA0001",
            "created_at": now
        }
        models_col.insert_one(m2_doc)
        print(f"✓ Created Model: {model2_name} ({model2_id})")
        m2 = m2_doc
    else:
        print(f"✓ Model {model2_name} already exists.")

    # 2. Seed Submodels (Graphics)
    print("\nSeeding Product Submodels...")
    subm1_name = "XOR MATTE RED/WHITE"
    subm2_name = "VINTAGE FULL FACE SOLID BLACK"

    sm1 = submodels_col.find_one({"name": subm1_name, "model_id": m1["model_id"]})
    if not sm1:
        submodel1_id = generate_custom_id("PSMD", submodels_col, "submodel_id")
        sm1_doc = {
            "submodel_id": submodel1_id,
            "name": subm1_name,
            "model_id": m1["model_id"],
            "model_name": m1["name"],
            "model_status": m1["is_active"],
            "model_is_active": m1["is_active"],
            "image": "/qrcodes/Brands/PBRD26AAAA0003/logo.png",
            "is_active": True,
            "box_weight": 1.4,
            "box_dimension": "35x25x25",
            "carton_weight": 8.5,
            "carton_dimension": "72x52x52",
            "packaging_details": "6 units per carton, individual box packaging.",
            "box_and_carton_dimensions": "Box: 35x25x25, Carton: 72x52x52",
            "carton_numbers": "BOX-CAR-01",
            "created_by": "EMP26AAAA0001",
            "created_at": now
        }
        submodels_col.insert_one(sm1_doc)
        print(f"✓ Created Submodel: {subm1_name} ({submodel1_id})")
        sm1 = sm1_doc
    else:
        print(f"✓ Submodel {subm1_name} already exists.")

    # Submodel 2
    sm2 = submodels_col.find_one({"name": subm2_name, "model_id": m2["model_id"]})
    if not sm2:
        submodel2_id = generate_custom_id("PSMD", submodels_col, "submodel_id")
        sm2_doc = {
            "submodel_id": submodel2_id,
            "name": subm2_name,
            "model_id": m2["model_id"],
            "model_name": m2["name"],
            "model_status": m2["is_active"],
            "model_is_active": m2["is_active"],
            "image": "/qrcodes/Brands/PBRD26AAAA0003/logo.png",
            "is_active": True,
            "box_weight": 1.6,
            "box_dimension": "36x26x26",
            "carton_weight": 9.8,
            "carton_dimension": "74x54x54",
            "packaging_details": "6 units per carton, individual box packaging.",
            "box_and_carton_dimensions": "Box: 36x26x26, Carton: 74x54x54",
            "carton_numbers": "BOX-CAR-02",
            "created_by": "EMP26AAAA0001",
            "created_at": now
        }
        submodels_col.insert_one(sm2_doc)
        print(f"✓ Created Submodel: {subm2_name} ({submodel2_id})")
        sm2 = sm2_doc
    else:
        print(f"✓ Submodel {subm2_name} already exists.")

    # 3. Seed Variants
    print("\nSeeding Product Variants...")
    sku1 = "CLASSIC-XOR-RED-L"
    sku2 = "CLASSIC-FF-BLK-M"

    # Variant 1
    v1 = variants_col.find_one({"sku_no": sku1})
    if not v1:
        v1_id = generate_custom_id("PVAR", variants_col, "variant_id")
        v1_doc = {
            "variant_id": v1_id,
            "sku_no": sku1,
            "submodel_id": sm1["submodel_id"],
            "gs1_barcode": "1234567890123",
            "short_description": "Retro classic design with maximum comfort.",
            "long_description": "Perfectly combines safety with style. High impact strength shell with retro decals.",
            "carton_box_size": 6,
            "carton_barcode": "1234567890999",
            "product_images": ["/qrcodes/Brands/PBRD26AAAA0003/logo.png"],
            "color": "Matte Red/White",
            "size_name": "L",
            "size": 59,
            "finish": "Matte",
            "certification": ["DOT", "ECE", "ISI"],
            "visor_type": "Clear",
            "spoiler": "No",
            "chinstrap_lock": "Double D-Ring",
            "pinlock": "Yes",
            "mrp": {"INR": 4500.0},
            "is_active": True,
            "created_by": "EMP26AAAA0001",
            "created_at": now
        }
        variants_col.insert_one(v1_doc)
        print(f"✓ Created Variant: {sku1} ({v1_id})")
    else:
        print(f"✓ Variant {sku1} already exists.")

    # Variant 2
    v2 = variants_col.find_one({"sku_no": sku2})
    if not v2:
        v2_id = generate_custom_id("PVAR", variants_col, "variant_id")
        v2_doc = {
            "variant_id": v2_id,
            "sku_no": sku2,
            "submodel_id": sm2["submodel_id"],
            "gs1_barcode": "1234567890124",
            "short_description": "Full face vintage design with optimal aerodynamic performance.",
            "long_description": "Premium leather interior padding, scratch resistant visor, lightweight shell.",
            "carton_box_size": 6,
            "carton_barcode": "1234567891000",
            "product_images": ["/qrcodes/Brands/PBRD26AAAA0003/logo.png"],
            "color": "Matte Black",
            "size_name": "M",
            "size": 57,
            "finish": "Matte",
            "certification": ["DOT", "ECE", "ISI"],
            "visor_type": "Smoke",
            "spoiler": "No",
            "chinstrap_lock": "Quick Release Micrometric buckle",
            "pinlock": "Yes",
            "mrp": {"INR": 5500.0},
            "is_active": True,
            "created_by": "EMP26AAAA0001",
            "created_at": now
        }
        variants_col.insert_one(v2_doc)
        print(f"✓ Created Variant: {sku2} ({v2_id})")
    else:
        print(f"✓ Variant {sku2} already exists.")

    print("\n✅ Seeding complete!")

if __name__ == "__main__":
    seed_products()
