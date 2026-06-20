import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException
from app import utils
from app.database import (
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection,
    product_variants_collection
)
from app.api.product_api import (
    ProductCategoryOperations,
    ProductSubCategoryOperations,
    ProductBrandOperations,
    ProductModelOperations,
    ProductSubModelOperations,
    ProductVariantOperations
)
from app.schemas import (
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductSubCategoryCreate,
    ProductSubCategoryUpdate,
    ProductBrandCreate,
    ProductBrandUpdate,
    ProductModelCreate,
    ProductModelUpdate,
    ProductSubModelCreate,
    ProductSubModelUpdate,
    ProductVariantCreate,
    ProductVariantUpdate
)

# Clean up any previous test data
product_categories_collection.delete_many({})
product_subcategories_collection.delete_many({})
product_brands_collection.delete_many({})
product_models_collection.delete_many({})
product_submodels_collection.delete_many({})
product_variants_collection.delete_many({})

print("=========================================")
print("RUNNING PRODUCT MASTER LOGIC VERIFICATION")
print("=========================================")

admin_user = {"user_id": "admin_01", "role": "Super Admin"}
yy = str(utils.get_current_time().year)[-2:]

# 1. Test Product Category
print("1. Testing Category CRUD and active status...")
cat_a = ProductCategoryOperations.create_category(
    ProductCategoryCreate(name="Helmets", is_active=True),
    current_user=admin_user
)
assert cat_a["category_id"] == f"PCAT{yy}AAAA0001"
assert cat_a["is_active"] is True
print(f"✓ ProductCategory created successfully with ID PCAT{yy}AAAA0001!")

# Try creating duplicate category
try:
    ProductCategoryOperations.create_category(
        ProductCategoryCreate(name="Helmets", is_active=True),
        current_user=admin_user
    )
    assert False, "Should raise HTTPException for duplicate name"
except HTTPException as e:
    assert e.status_code == 400
    print("✓ Duplicate Category blocked successfully!")

# Update Category Active Status
updated_cat = ProductCategoryOperations.update_category(
    f"PCAT{yy}AAAA0001",
    ProductCategoryUpdate(is_active=False)
)
assert updated_cat["is_active"] is False
print("✓ ProductCategory updated successfully to inactive!")

# 2. Test Product Sub Category
print("\n2. Testing Sub Category CRUD and active status...")
sub_a = ProductSubCategoryOperations.create_subcategory(
    ProductSubCategoryCreate(name="Full Face Helmets", category_id=f"PCAT{yy}AAAA0001", is_active=True),
    current_user=admin_user
)
assert sub_a["subcategory_id"] == f"PSUB{yy}AAAA0001"
assert sub_a["is_active"] is True
print(f"✓ ProductSubCategory created successfully with ID PSUB{yy}AAAA0001!")

# Update Subcategory Active Status
updated_sub = ProductSubCategoryOperations.update_subcategory(
    f"PSUB{yy}AAAA0001",
    ProductSubCategoryUpdate(is_active=False)
)
assert updated_sub["is_active"] is False
print("✓ ProductSubCategory updated successfully to inactive status!")

# 3. Test Brand
print("\n3. Testing Brand CRUD, Logo, and active status...")
brand_a = ProductBrandOperations.create_brand(
    name="Vega",
    description="Premium Helmets & Accessories",
    logo=None,
    is_active=True,
    size_master=[["xs", 600, f"PCAT{yy}AAAA0001"], ["s", 800, f"PCAT{yy}AAAA0001"], ["xl", 1200, f"PCAT{yy}AAAA0001"]],
    current_user=admin_user
)
assert brand_a["brand_id"] == f"PBRD{yy}AAAA0001"
assert brand_a["is_active"] is True
assert len(brand_a["size_master"]) == 3
print(f"✓ ProductBrand created successfully with ID PBRD{yy}AAAA0001 and size_master!")

# Update Brand Active Status
updated_brand = ProductBrandOperations.update_brand(
    brand_id=f"PBRD{yy}AAAA0001",
    name=None,
    description=None,
    logo=None,
    is_active=True,
    size_master=[["xs", 600, f"PCAT{yy}AAAA0001"], ["s", 800, f"PCAT{yy}AAAA0001"], ["xl", 1200, f"PCAT{yy}AAAA0001"], ["xxl", 1400, f"PCAT{yy}AAAA0001"]]
)
assert updated_brand["is_active"] is True
assert len(updated_brand["size_master"]) == 4
print("✓ ProductBrand updated successfully with new size_master!")

# 4. Test Model
print("\n4. Testing Model CRU and active status...")
model_a = ProductModelOperations.create_model(
    ProductModelCreate(
        name="Bolt",
        brand_id=f"PBRD{yy}AAAA0001",
        category_id=f"PCAT{yy}AAAA0001",
        subcategory_id=f"PSUB{yy}AAAA0001",
        is_active=True
    ),
    current_user=admin_user
)
assert model_a["model_id"] == f"PMOD{yy}AAAA0001"
assert model_a["is_active"] is True
print(f"✓ ProductModel created successfully with ID PMOD{yy}AAAA0001!")

# Update Model Active Status
updated_model = ProductModelOperations.update_model(
    f"PMOD{yy}AAAA0001",
    ProductModelUpdate(is_active=False)
)
assert updated_model["is_active"] is False
print("✓ ProductModel updated successfully to inactive status!")

# 5. Test Submodel
print("\n5. Testing Submodel / Graphic CRU and active status...")
submodel_a = ProductSubModelOperations.create_submodel(
    ProductSubModelCreate(
        name="Red Decal Graphic",
        model_id=f"PMOD{yy}AAAA0001",
        image="https://cdn.example.com/submodel-red-decal.png",
        is_active=True,
        box_weight=1.65,
        box_dimension="35x25x25",
        carton_weight=10.2,
        carton_dimension="75x55x30",
        packaging_details="Packaging details for Bolt Red",
        box_and_carton_dimensions="Box: 35x25x25, Carton: 75x55x30",
        carton_numbers="BOLT-RED-CAR"
    ),
    image_file=None,
    images=[],
    certification=[],
    current_user=admin_user
)
assert submodel_a["submodel_id"] == f"PSMD{yy}AAAA0001"
assert submodel_a["image"] == "https://cdn.example.com/submodel-red-decal.png"
assert submodel_a["is_active"] is True
print(f"✓ ProductSubModel created successfully with ID PSMD{yy}AAAA0001!")

# Update Submodel Active Status
updated_submodel = ProductSubModelOperations.update_submodel(
    f"PSMD{yy}AAAA0001",
    ProductSubModelUpdate(is_active=False),
    name=None,
    image_file=None
)
assert updated_submodel["is_active"] is False
print("✓ ProductSubModel updated successfully to inactive status!")

# 6. Test Variant
print("\n6. Testing Variant CRU, SKU, and dynamic parent mapping...")
variant_a = ProductVariantOperations.create_variant(
    ProductVariantCreate(
        sku_no="VEGA-BOLT-M-RED",
        submodel_id=f"PSMD{yy}AAAA0001",
        gs1_barcode="8901234567890",
        short_description="Vega Bolt Medium Red Decal",
        long_description="High impact ABS material shell helmet with red decals.",
        carton_box_size=4,
        carton_barcode="8901234567890-C",
        product_images=["https://cdn.example.com/vega-red.jpg"],
        color="Red",
        size_name="Medium",
        size=58,
        finish="Gloss",
        certification=["DOT", "ISI"],
        visor_type="Double Visor",
        spoiler="Integrated",
        chinstrap_lock="Quick Release",
        pinlock="Optional",
        mrp={"INR": 1850.0},
        is_active=True
    ),
    current_user=admin_user
)
assert variant_a["variant_id"] == f"PVAR{yy}AAAA0001"
assert variant_a["sku_no"] == "VEGA-BOLT-M-RED"
assert variant_a["mrp"] == {"INR": 1850.0}
assert variant_a["carton_box_size"] == 4
assert variant_a["carton_barcode"] == "8901234567890-C"
assert variant_a["submodel_name"] == "Red Decal Graphic"
assert variant_a["submodel_image"] == "https://cdn.example.com/submodel-red-decal.png"
assert variant_a["model_name"] == "Bolt"
assert variant_a["brand_name"] == "Vega"
assert variant_a["category_name"] == "Helmets"
assert variant_a["subcategory_name"] == "Full Face Helmets"
print(f"✓ ProductVariant created with sequential ID {variant_a['variant_id']}!")
print(f"✓ Dynamically resolved Category: {variant_a['category_name']}, Subcategory: {variant_a['subcategory_name']}, Brand: {variant_a['brand_name']}, Model: {variant_a['model_name']}, Submodel: {variant_a['submodel_name']}")

# Create Sister ProductVariant to test dynamic details
variant_a2 = ProductVariantOperations.create_variant(
    ProductVariantCreate(
        sku_no="VEGA-BOLT-L-RED",
        submodel_id=f"PSMD{yy}AAAA0001",
        gs1_barcode="8901234567999",
        short_description="Vega Bolt Large Red Decal",
        long_description="High impact ABS material shell helmet with red decals, size Large.",
        product_images=["https://cdn.example.com/vega-red-l.jpg"],
        color="Red",
        size_name="XS",
        finish="Gloss",
        certification=["DOT", "ISI"],
        visor_type="Double Visor",
        spoiler="Integrated",
        chinstrap_lock="Quick Release",
        pinlock="Optional",
        mrp={"INR": 1900.0},
        is_active=True
    ),
    current_user=admin_user
)
assert variant_a2["variant_id"] == f"PVAR{yy}AAAA0002"
assert variant_a2["size"] == 600
assert variant_a2["mrp"] == {"INR": 1900.0}
print(f"✓ Sister ProductVariant created with ID {variant_a2['variant_id']} (size auto-resolved to 600)!")

# Fetch detail of variant_a and verify sister_variants list contains variant_a2 details
detail_a = ProductVariantOperations.get_variant_detail(f"PVAR{yy}AAAA0001")
assert "sister_variants" in detail_a
assert len(detail_a["sister_variants"]) == 1
assert detail_a["sister_variants"][0]["variant_id"] == f"PVAR{yy}AAAA0002"
assert detail_a["sister_variants"][0]["sku_no"] == "VEGA-BOLT-L-RED"
assert detail_a["sister_variants"][0]["size"] == 600
assert detail_a["submodel_image"] == "https://cdn.example.com/submodel-red-decal.png"
print("✓ Variant detail with sister_variants resolved and asserted successfully!")

# Check SKU uniqueness
try:
    ProductVariantOperations.create_variant(
        ProductVariantCreate(
            sku_no="VEGA-BOLT-M-RED",
            submodel_id=f"PSMD{yy}AAAA0001",
            is_active=True
        ),
        current_user=admin_user
    )
    assert False, "Should raise HTTPException for duplicate SKU"
except HTTPException as e:
    assert e.status_code == 400
    print("✓ Duplicate SKU check passed!")

# Test Submodel Filter Query
all_vars_filtered = ProductVariantOperations.get_variants(submodel_id=f"PSMD{yy}AAAA0001")
assert len(all_vars_filtered) == 2
assert all_vars_filtered[0]["sku_no"] == "VEGA-BOLT-M-RED"
print("✓ Submodel query filtering validation passed!")

# Test Dynamic Cards Filters
# filter by brand_id
vars_brand_filtered = ProductVariantOperations.filter_variants(brand_id=f"PBRD{yy}AAAA0001")
assert len(vars_brand_filtered) == 2
assert vars_brand_filtered[0]["sku_no"] == "VEGA-BOLT-M-RED"

# filter by color (case-insensitive)
vars_color_filtered = ProductVariantOperations.filter_variants(color="Red")
assert len(vars_color_filtered) == 2

# filter by search term
vars_search_filtered = ProductVariantOperations.filter_variants(search="decal")
assert len(vars_search_filtered) == 2

# filter by visor_type (case-insensitive)
vars_visor_filtered = ProductVariantOperations.filter_variants(visor_type="Double Visor")
assert len(vars_visor_filtered) == 2

# filter by spoiler (case-insensitive)
vars_spoiler_filtered = ProductVariantOperations.filter_variants(spoiler="Integrated")
assert len(vars_spoiler_filtered) == 2

# filter by pinlock (case-insensitive)
vars_pinlock_filtered = ProductVariantOperations.filter_variants(pinlock="Optional")
assert len(vars_pinlock_filtered) == 2

# filter by size (integer)
vars_size_filtered = ProductVariantOperations.filter_variants(size=58)
assert len(vars_size_filtered) == 1
assert vars_size_filtered[0]["sku_no"] == "VEGA-BOLT-M-RED"

# filter by certification (matching dot)
vars_cert_filtered_dot = ProductVariantOperations.filter_variants(certification="DOT")
assert len(vars_cert_filtered_dot) == 2

# filter by certification (matching isi)
vars_cert_filtered_isi = ProductVariantOperations.filter_variants(certification="ISI")
assert len(vars_cert_filtered_isi) == 2

print("✓ Dynamic product card query filtering validation passed!")

# Update Variant Active Status, size and certification
updated_variant = ProductVariantOperations.update_variant(
    f"PVAR{yy}AAAA0001",
    ProductVariantUpdate(
        is_active=False,
        mrp={"INR": 2200.0},
        carton_box_size=6,
        carton_barcode="8901234567890-C-UPDATED",
        size=62,
        certification=["DOT", "ISI", "ECE"]
    )
)
assert updated_variant["is_active"] is False
assert updated_variant["mrp"] == {"INR": 2200.0}
assert updated_variant["carton_box_size"] == 6
assert updated_variant["carton_barcode"] == "8901234567890-C-UPDATED"
assert updated_variant["size"] == 62
assert updated_variant["certification"] == ["DOT", "ISI", "ECE"]
print("✓ ProductVariant updated successfully with new MRP, Carton Box Size, Carton Barcode, size, and certification!")

# 7. Test Bulk MRP updates
print("\n7. Testing Bulk Variant MRP and Multi-Currency update...")
bulk_res = ProductVariantOperations.update_mrp_bulk(
    variant_ids=[f"PVAR{yy}AAAA0001", f"PVAR{yy}AAAA0002"],
    mrp={"USD": 25.0, "EUR": 22.0}
)
assert bulk_res["status"] == "success"
assert bulk_res["updated_count"] == 2

# Verify updates merged correctly
v1_updated = product_variants_collection.find_one({"variant_id": f"PVAR{yy}AAAA0001"})
v2_updated = product_variants_collection.find_one({"variant_id": f"PVAR{yy}AAAA0002"})

assert "USD" in v1_updated["mrp"]
assert v1_updated["mrp"]["USD"] == 25.0
assert "EUR" in v1_updated["mrp"]
assert v1_updated["mrp"]["EUR"] == 22.0

assert "USD" in v2_updated["mrp"]
assert v2_updated["mrp"]["USD"] == 25.0
assert "EUR" in v2_updated["mrp"]
assert v2_updated["mrp"]["EUR"] == 22.0

print("✓ Bulk Variant MRP/currency update passed!")

# Clean up
product_categories_collection.delete_many({})
product_subcategories_collection.delete_many({})
product_brands_collection.delete_many({})
product_models_collection.delete_many({})
product_submodels_collection.delete_many({})
product_variants_collection.delete_many({})

print("\n=========================================")
print("✓ ALL PRODUCT MASTER LOGIC TESTS PASSED!")
print("=========================================")
