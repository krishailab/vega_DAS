import os
from pymongo import MongoClient
from dotenv import load_dotenv
import certifi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())

db = client["vega_track"]

users_collection = db["users"]
stations_collection = db["stations"]
job_cards_collection = db["job_cards"]
qr_master_collection = db["qr_master"]
products_collection = db["products"]
scanner_processes_collection = db["scanner_processes"]
assembly_processes_collection = db["assembly_processes"]
dispatch_processes_collection = db["dispatch_processes"]
parts_collection = db["parts"]
shifts_collection = db["shifts"]
processes_collection = db["processes"]
reasons_collection = db["reasons"]
asset_categories_collection = db["asset_categories"]
asset_subcategories_collection = db["asset_subcategories"]
assets_collection = db["assets"]
asset_assignments_collection = db["asset_assignments"]
asset_submissions_collection = db["asset_submissions"]
kiosks_collection = db["kiosks"]
product_categories_collection = db["product_categories"]
product_subcategories_collection = db["product_subcategories"]
product_brands_collection = db["product_brands"]
product_models_collection = db["product_models"]
product_submodels_collection = db["product_submodels"]
product_variants_collection = db["product_variants"]
plants_collection = db["plants"]
dealer_signup_requests_collection = db["dealer_signup_requests"]
b2b_inward_products_collection = db["b2b_inward_products"]
b2b_cart_collection = db["b2b_cart"]
b2b_orders_collection = db["b2b_orders"]
b2b_invoices_collection = db["b2b_invoices"]
b2b_coupons_collection = db["b2b_coupons"]
b2b_config_collection = db["b2b_config"]
b2b_gst_settings_collection = db["b2b_gst_settings"]


coin_config_collection    = db["coin_config"]     
coin_wallets_collection   = db["coin_wallets"]      
coin_transactions_collection = db["coin_transactions"] 

def safe_create_index(collection, keys, **kwargs):
    try:
        collection.create_index(keys, **kwargs)
    except Exception as ie:
        if "IndexKeySpecsConflict" in str(ie) or "already exists with different options" in str(ie) or getattr(ie, 'code', None) == 86:
            pass
        else:
            print(f"Warning: Failed to create index on {collection.name} for {keys}: {ie}")

try:
    safe_create_index(qr_master_collection, "qr_id", unique=True)
    safe_create_index(qr_master_collection, "part_id")
    safe_create_index(scanner_processes_collection, "scan_id")
    safe_create_index(scanner_processes_collection, "qr_id")
    safe_create_index(scanner_processes_collection, "scanner_id")
    safe_create_index(scanner_processes_collection, "start_time")
    safe_create_index(assembly_processes_collection, "assembly_id")
    safe_create_index(assembly_processes_collection, "qr_id")
    safe_create_index(assembly_processes_collection, "linker_id")
    safe_create_index(assembly_processes_collection, "start_time")
    safe_create_index(dispatch_processes_collection, "dispatch_id")
    safe_create_index(dispatch_processes_collection, "qr_id")
    safe_create_index(dispatch_processes_collection, "linker_id")
    safe_create_index(dispatch_processes_collection, "start_time")

    # B2B Catalog indexes
    safe_create_index(product_categories_collection, "category_id", unique=True)
    safe_create_index(product_subcategories_collection, "subcategory_id", unique=True)
    safe_create_index(product_brands_collection, "brand_id", unique=True)
    safe_create_index(product_models_collection, "model_id", unique=True)
    safe_create_index(product_submodels_collection, "submodel_id", unique=True)
    
    # Variant and inward indexes
    safe_create_index(product_variants_collection, "variant_id", unique=True)
    safe_create_index(product_variants_collection, "submodel_id")
    safe_create_index(b2b_inward_products_collection, "inward_id", unique=True)
    safe_create_index(b2b_inward_products_collection, "variant_id")

    # Cart, Users and Orders indexes
    safe_create_index(users_collection, "user_id", unique=True)
    safe_create_index(b2b_cart_collection, [("user_id", 1), ("inward_id", 1)], unique=True)
    safe_create_index(b2b_orders_collection, "order_id", unique=True)
    safe_create_index(b2b_orders_collection, "user_id")
except Exception as e:
    print(f"Warning: Failed to ensure database indexes: {e}")



