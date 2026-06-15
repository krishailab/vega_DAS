import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import UploadFile
from app.api.product_api import ProductVariantOperations
from app.database import product_variants_collection

# Clean up existing test variant SKUs to avoid duplicate errors
product_variants_collection.delete_many({"sku_no": {"$in": ["VEGA-BOLT-M-RED", "VEGA-BOLT-L-RED"]}})

# Open the files as UploadFile
with open("axor.png", "rb") as f1, open("vega.png", "rb") as f2:
    upload_f1 = UploadFile(file=f1, filename="axor.png")
    upload_f2 = UploadFile(file=f2, filename="vega.png")
    
    parsed_variants = [
        ["M", 58, "VEGA-BOLT-M-RED", "Red", ["axor.png"]],
        ["L", 60, "VEGA-BOLT-L-RED", "Red", ["vega.png"]]
    ]
    
    admin_user = {"user_id": "admin_01", "role": "Super Admin"}
    
    res = ProductVariantOperations.create_variants_list(
        submodel_id="PSMD26A0001",
        parsed_variants=parsed_variants,
        images=[upload_f1, upload_f2],
        current_user=admin_user
    )
    print("Variants created successfully:")
    for v in res["variants"]:
        print(f"- ID: {v['variant_id']}, SKU: {v['sku_no']}, Images: {v['product_images']}")
