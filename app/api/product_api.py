import os
import shutil
from typing import Optional, List, Union
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Query
from .. import schemas, auth, utils
from ..database import (
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection,
    product_variants_collection
)

router = APIRouter(prefix="/api/v1/product-master", tags=["Product Master"])

def validate_size_master(size_master: Optional[Union[list, str]]) -> list:
    if size_master is None:
        return []
    
    parsed = size_master
    if isinstance(size_master, str):
        try:
            import json
            parsed = json.loads(size_master)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid size_master format. Must be a valid JSON array.")
    
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="size_master must be a list")
        
    for item in parsed:
        if not isinstance(item, list) or len(item) != 3:
            raise HTTPException(status_code=400, detail="Each size_master entry must be a list of 3 elements: [size_name, size, category_id]")
        if not isinstance(item[0], str):
            raise HTTPException(status_code=400, detail="Size name must be a string")
        if not isinstance(item[1], (int, float)):
            raise HTTPException(status_code=400, detail="Size value must be a number")
        if not isinstance(item[2], str):
            raise HTTPException(status_code=400, detail="Category ID must be a string")
        category_id = item[2].strip()
        if not product_categories_collection.find_one({"category_id": category_id}):
            raise HTTPException(status_code=400, detail=f"Category with ID '{category_id}' does not exist")
            
    return parsed

def resolve_size_from_brand(brand: Optional[dict], category_id: Optional[str], size_name: Optional[str]) -> Optional[int]:
    if not brand or not category_id or not size_name:
        return None
    size_master = brand.get("size_master", []) or []
    for entry in size_master:
        if len(entry) == 3:
            entry_size_name, entry_size, entry_category_id = entry
            if str(entry_size_name).strip().lower() == str(size_name).strip().lower() and str(entry_category_id).strip() == str(category_id).strip():
                return int(entry_size)
    return None

class ProductCategoryOperations:
    @staticmethod
    def create_category(category: schemas.ProductCategoryCreate, current_user: dict):
        if product_categories_collection.find_one({"name": category.name}):
            raise HTTPException(status_code=400, detail="Product category already exists")

        category_dict = category.model_dump()
        category_id = utils.generate_custom_id("PCAT", product_categories_collection, "category_id")
        category_dict["category_id"] = category_id
        category_dict["created_by"] = current_user["user_id"]
        category_dict["created_at"] = utils.get_current_time()

        product_categories_collection.insert_one(category_dict)
        category_dict.pop("_id", None)
        return category_dict

    @staticmethod
    def get_categories(page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"category_id": {"$regex": search, "$options": "i"}}
            ]
        total_count = product_categories_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        categories = list(product_categories_collection.find(query).skip(skip).limit(limit))
        for c in categories:
            c.pop("_id", None)
        return {
            "categories": categories,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_category(category_id: str, category: schemas.ProductCategoryUpdate):
        existing = product_categories_collection.find_one({"category_id": category_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product category not found")

        update_data = category.model_dump(exclude_unset=True)
        if update_data:
            product_categories_collection.update_one({"category_id": category_id}, {"$set": update_data})

        updated = product_categories_collection.find_one({"category_id": category_id})
        updated.pop("_id", None)
        return updated

class ProductSubCategoryOperations:
    @staticmethod
    def create_subcategory(subcategory: schemas.ProductSubCategoryCreate, current_user: dict):
        # Validate parent category
        category = product_categories_collection.find_one({"category_id": subcategory.category_id})
        if not category:
            raise HTTPException(status_code=404, detail="Parent Product category not found")

        if product_subcategories_collection.find_one({
            "name": subcategory.name,
            "category_id": subcategory.category_id
        }):
            raise HTTPException(status_code=400, detail="Product subcategory already exists under this category")

        sub_dict = subcategory.model_dump()
        subcategory_id = utils.generate_custom_id("PSUB", product_subcategories_collection, "subcategory_id")
        sub_dict["subcategory_id"] = subcategory_id
        sub_dict["category_name"] = category.get("name")
        sub_dict["category_status"] = category.get("is_active")
        sub_dict["category_is_active"] = category.get("is_active")
        sub_dict["created_by"] = current_user["user_id"]
        sub_dict["created_at"] = utils.get_current_time()

        product_subcategories_collection.insert_one(sub_dict)
        sub_dict.pop("_id", None)
        return sub_dict

    @staticmethod
    def get_subcategories(page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"subcategory_id": {"$regex": search, "$options": "i"}},
                {"category_name": {"$regex": search, "$options": "i"}}
            ]
        total_count = product_subcategories_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        subcategories = list(product_subcategories_collection.find(query).skip(skip).limit(limit))
        for s in subcategories:
            s.pop("_id", None)
            category = product_categories_collection.find_one({"category_id": s["category_id"]})
            s["category_name"] = category.get("name") if category else None
            s["category_status"] = category.get("is_active") if category else None
            s["category_is_active"] = category.get("is_active") if category else None
        return {
            "subcategories": subcategories,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_subcategory(subcategory_id: str, subcategory: schemas.ProductSubCategoryUpdate):
        existing = product_subcategories_collection.find_one({"subcategory_id": subcategory_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product subcategory not found")

        update_data = subcategory.model_dump(exclude_unset=True)
        if update_data:
            product_subcategories_collection.update_one({"subcategory_id": subcategory_id}, {"$set": update_data})

        updated = product_subcategories_collection.find_one({"subcategory_id": subcategory_id})
        updated.pop("_id", None)
        
        category = product_categories_collection.find_one({"category_id": updated["category_id"]})
        updated["category_name"] = category.get("name") if category else None
        updated["category_status"] = category.get("is_active") if category else None
        updated["category_is_active"] = category.get("is_active") if category else None
        return updated

class ProductBrandOperations:
    @staticmethod
    def create_brand(
        name: str,
        description: Optional[str],
        logo: Optional[UploadFile],
        is_active: bool,
        size_master: Optional[Union[list, str]],
        current_user: dict
    ):
        if product_brands_collection.find_one({"name": name}):
            raise HTTPException(status_code=400, detail="Product brand already exists")

        brand_id = utils.generate_custom_id("PBRD", product_brands_collection, "brand_id")
        
        logo_url = None
        if logo and logo.filename:
            base_dir = os.path.join("qrcodes", "Brands", brand_id)
            os.makedirs(base_dir, exist_ok=True)
            ext = os.path.splitext(logo.filename)[1] or ".png"
            logo_path = os.path.join(base_dir, f"logo{ext}")
            with open(logo_path, "wb") as buf:
                shutil.copyfileobj(logo.file, buf)
            logo_url = f"/qrcodes/Brands/{brand_id}/logo{ext}"

        parsed_size_master = validate_size_master(size_master)

        brand_dict = {
            "brand_id": brand_id,
            "name": name,
            "description": description,
            "logo_url": logo_url,
            "is_active": is_active,
            "size_master": parsed_size_master,
            "created_by": current_user["user_id"],
            "created_at": utils.get_current_time()
        }

        product_brands_collection.insert_one(brand_dict)
        brand_dict.pop("_id", None)
        return brand_dict

    @staticmethod
    def get_brands(page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"brand_id": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        total_count = product_brands_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        brands = list(product_brands_collection.find(query).skip(skip).limit(limit))
        for b in brands:
            b.pop("_id", None)
        return {
            "brands": brands,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_brand(
        brand_id: str,
        brand: schemas.ProductBrandUpdate
    ):
        existing = product_brands_collection.find_one({"brand_id": brand_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product brand not found")

        update_data = {}
        if brand.is_active is not None:
            update_data["is_active"] = brand.is_active
        if brand.name is not None:
            update_data["name"] = brand.name
        if brand.description is not None:
            update_data["description"] = brand.description
        if brand.size_master is not None:
            update_data["size_master"] = validate_size_master(brand.size_master)

        if update_data:
            product_brands_collection.update_one({"brand_id": brand_id}, {"$set": update_data})

        updated = product_brands_collection.find_one({"brand_id": brand_id})
        updated.pop("_id", None)
        return updated

class ProductModelOperations:
    @staticmethod
    def create_model(model: schemas.ProductModelCreate, current_user: dict):
        # Validate parent subcategory first to inherit category_id if not provided
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model.subcategory_id})
        if not subcategory:
            raise HTTPException(status_code=404, detail="Product subcategory not found")

        category_id = model.category_id or subcategory.get("category_id")
        if not category_id:
            raise HTTPException(status_code=400, detail="Product category_id is required or must be linked to the subcategory")

        # Validate parent category
        category = product_categories_collection.find_one({"category_id": category_id})
        if not category:
            raise HTTPException(status_code=404, detail="Product category not found")

        # Validate parent brand
        brand = product_brands_collection.find_one({"brand_id": model.brand_id})
        if not brand:
            raise HTTPException(status_code=404, detail="Product brand not found")

        if product_models_collection.find_one({
            "name": model.name,
            "brand_id": model.brand_id,
            "category_id": category_id,
            "subcategory_id": model.subcategory_id
        }):
            raise HTTPException(status_code=400, detail="Product model already exists with these parameters")

        model_dict = model.model_dump()
        model_dict["category_id"] = category_id
        model_id = utils.generate_custom_id("PMOD", product_models_collection, "model_id")
        model_dict["model_id"] = model_id
        
        # Populate referenced info
        model_dict["brand_name"] = brand.get("name")
        model_dict["brand_status"] = brand.get("is_active")
        model_dict["brand_is_active"] = brand.get("is_active")
        model_dict["brand_image"] = brand.get("logo_url")
        
        model_dict["category_name"] = category.get("name")
        model_dict["category_status"] = category.get("is_active")
        model_dict["category_is_active"] = category.get("is_active")
        
        model_dict["subcategory_name"] = subcategory.get("name")
        model_dict["subcategory_status"] = subcategory.get("is_active")
        model_dict["subcategory_is_active"] = subcategory.get("is_active")

        model_dict["created_by"] = current_user["user_id"]
        model_dict["created_at"] = utils.get_current_time()

        product_models_collection.insert_one(model_dict)
        model_dict.pop("_id", None)
        return model_dict

    @staticmethod
    def get_models(page: int = 1, limit: int = 50, search: str = "", brand_id: Optional[str] = None, is_active: Optional[bool] = None):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"model_id": {"$regex": search, "$options": "i"}},
                {"brand_name": {"$regex": search, "$options": "i"}},
                {"category_name": {"$regex": search, "$options": "i"}},
                {"subcategory_name": {"$regex": search, "$options": "i"}}
            ]
        if brand_id is not None:
            query["brand_id"] = brand_id
        if is_active is not None:
            query["is_active"] = is_active
        total_count = product_models_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        models = list(product_models_collection.find(query).skip(skip).limit(limit))
        for m in models:
            m.pop("_id", None)
            # Resolve Brand Info
            brand = product_brands_collection.find_one({"brand_id": m["brand_id"]})
            m["brand_name"] = brand.get("name") if brand else None
            m["brand_status"] = brand.get("is_active") if brand else None
            m["brand_is_active"] = brand.get("is_active") if brand else None
            m["brand_image"] = brand.get("logo_url") if brand else None
            
            # Resolve Category Info
            category = product_categories_collection.find_one({"category_id": m["category_id"]})
            m["category_name"] = category.get("name") if category else None
            m["category_status"] = category.get("is_active") if category else None
            m["category_is_active"] = category.get("is_active") if category else None
            
            # Resolve Subcategory Info
            subcategory = product_subcategories_collection.find_one({"subcategory_id": m["subcategory_id"]})
            m["subcategory_name"] = subcategory.get("name") if subcategory else None
            m["subcategory_status"] = subcategory.get("is_active") if subcategory else None
            m["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None
        return {
            "models": models,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_model(model_id: str, model: schemas.ProductModelUpdate):
        existing = product_models_collection.find_one({"model_id": model_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product model not found")

        update_data = model.model_dump(exclude_unset=True)
        if update_data:
            product_models_collection.update_one({"model_id": model_id}, {"$set": update_data})

        updated = product_models_collection.find_one({"model_id": model_id})
        updated.pop("_id", None)
        
        # Resolve Brand Info
        brand = product_brands_collection.find_one({"brand_id": updated["brand_id"]})
        updated["brand_name"] = brand.get("name") if brand else None
        updated["brand_status"] = brand.get("is_active") if brand else None
        updated["brand_is_active"] = brand.get("is_active") if brand else None
        updated["brand_image"] = brand.get("logo_url") if brand else None
        
        # Resolve Category Info
        category = product_categories_collection.find_one({"category_id": updated["category_id"]})
        updated["category_name"] = category.get("name") if category else None
        updated["category_status"] = category.get("is_active") if category else None
        updated["category_is_active"] = category.get("is_active") if category else None
        
        # Resolve Subcategory Info
        subcategory = product_subcategories_collection.find_one({"subcategory_id": updated["subcategory_id"]})
        updated["subcategory_name"] = subcategory.get("name") if subcategory else None
        updated["subcategory_status"] = subcategory.get("is_active") if subcategory else None
        updated["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None
        return updated

class ProductSubModelOperations:
    @staticmethod
    def create_submodel(
        submodel: schemas.ProductSubModelCreate, 
        image_file: Optional[UploadFile] = None, 
        images: List[Union[UploadFile, str]] = None, 
        current_user: dict = None
    ):
        # Validate parent model
        model = product_models_collection.find_one({"model_id": submodel.model_id})
        if not model:
            raise HTTPException(status_code=404, detail="Product model not found")

        if product_submodels_collection.find_one({
            "name": submodel.name,
            "model_id": submodel.model_id
        }):
            raise HTTPException(status_code=400, detail="Product submodel/graphic already exists under this model")

        submodel_id = utils.generate_custom_id("PSMD", product_submodels_collection, "submodel_id")
        
        base_dir = os.path.join("qrcodes", "Submodels", submodel_id)

        # Save product_images
        product_image_urls = []
        for img in images:
            if hasattr(img, "file") and img.filename:
                os.makedirs(base_dir, exist_ok=True)
                ext = os.path.splitext(img.filename)[1] or ".png"
                img_name = f"product_image_{len(product_image_urls)}{ext}"
                img_path = os.path.join(base_dir, img_name)
                with open(img_path, "wb") as buf:
                    shutil.copyfileobj(img.file, buf)
                product_image_urls.append(f"/qrcodes/Submodels/{submodel_id}/{img_name}")
            elif isinstance(img, str) and img.strip():
                product_image_urls.append(img.strip())

        # Removed certification saving logic here
        submodel_dict = {
            "submodel_id": submodel_id,
            "name": submodel.name,
            "model_id": submodel.model_id,
            "is_active": submodel.is_active,
            
            # Variant fields stored on submodel
            "short_description": submodel.short_description,
            "long_description": submodel.long_description,
            "product_images": product_image_urls,
            "visor_type": submodel.visor_type,
            "spoiler": submodel.spoiler,
            "pinlock": submodel.pinlock,
            "style": submodel.style,
            
            "model_name": model.get("name"),
            "model_status": model.get("is_active"),
            "model_is_active": model.get("is_active"),
            "model_chinstrap_lock": model.get("chinstrap_lock"),
            "brand_id": (product_brands_collection.find_one({"brand_id": model.get("brand_id")}) or {}).get("brand_id") if model else None,
            "brand_name": (product_brands_collection.find_one({"brand_id": model.get("brand_id")}) or {}).get("name") if model else None,
            "created_by": current_user["user_id"] if current_user else "SYSTEM",
            "created_at": utils.get_current_time()
        }

        product_submodels_collection.insert_one(submodel_dict)
        submodel_dict.pop("_id", None)
        submodel_dict["variants"] = []
        return submodel_dict

    @staticmethod
    def get_submodels(page: int = 1, limit: int = 50, search: str = "", model_id: Optional[str] = None, brand_id: Optional[str] = None, is_active: Optional[bool] = None):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"submodel_id": {"$regex": search, "$options": "i"}},
                {"model_name": {"$regex": search, "$options": "i"}},
                {"brand_name": {"$regex": search, "$options": "i"}}
            ]
        if model_id is not None:
            query["model_id"] = model_id
        if brand_id is not None:
            query["brand_id"] = brand_id
        if is_active is not None:
            query["is_active"] = is_active
        total_count = product_submodels_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        
        skip = (page - 1) * limit
        submodels = list(product_submodels_collection.find(query).skip(skip).limit(limit))
        
        # Bulk fetch Models
        model_ids = list({s["model_id"] for s in submodels if s.get("model_id")})
        models = list(product_models_collection.find({"model_id": {"$in": model_ids}})) if model_ids else []
        models_dict = {m["model_id"]: m for m in models}
        
        # Bulk fetch Brands
        brand_ids = list({m.get("brand_id") for m in models if m.get("brand_id")})
        brands = list(product_brands_collection.find({"brand_id": {"$in": brand_ids}})) if brand_ids else []
        brands_dict = {b["brand_id"]: b for b in brands}
        
        # Bulk fetch and trim Variants
        submodel_ids = [s["submodel_id"] for s in submodels if s.get("submodel_id")]
        variants = list(product_variants_collection.find(
            {"submodel_id": {"$in": submodel_ids}},
            {"_id": 0, "variant_id": 1, "sku_no": 1, "size": 1, "size_name": 1, "color": 1, "product_images": 1, "submodel_id": 1,
             "finish": 1, "mrp": 1, "gs1_barcode": 1, "carton_barcode": 1, "is_active": 1}
        )) if submodel_ids else []
        
        variants_by_submodel = {}
        for v in variants:
            sub_id = v.get("submodel_id")
            if sub_id not in variants_by_submodel:
                variants_by_submodel[sub_id] = []
            variants_by_submodel[sub_id].append({
                "variant_id": v.get("variant_id"),
                "sku_no": v.get("sku_no"),
                "size": v.get("size"),
                "size_name": v.get("size_name"),
                "color": v.get("color"),
                "product_images": v.get("product_images", []),
                "finish": v.get("finish"),
                "mrp": v.get("mrp"),
                "gs1_barcode": v.get("gs1_barcode"),
                "carton_barcode": v.get("carton_barcode"),
                "is_active": v.get("is_active", True)
            })
            
        for s in submodels:
            s.pop("_id", None)
            # Resolve Model Info
            model = models_dict.get(s.get("model_id"))
            s["model_name"] = model.get("name") if model else None
            s["model_status"] = model.get("is_active") if model else None
            s["model_is_active"] = model.get("is_active") if model else None
            s["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None
            
            # Resolve Brand Info
            brand = brands_dict.get(model.get("brand_id")) if model else None
            s["brand_id"] = brand.get("brand_id") if brand else None
            s["brand_name"] = brand.get("name") if brand else None
            s["brand_image"] = brand.get("logo_url") if brand else None
            
            s["variants"] = variants_by_submodel.get(s["submodel_id"], [])
            
        return {
            "submodels": submodels,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_submodel(
        submodel_id: str, 
        submodel: schemas.ProductSubModelUpdate, 
        name: Optional[str] = None, 
        image_file: Optional[UploadFile] = None,
        images: Optional[List[Union[UploadFile, str]]] = None,
        current_user: Optional[dict] = None
    ):
        existing = product_submodels_collection.find_one({"submodel_id": submodel_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product submodel not found")

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if submodel.is_active is not None:
            update_data["is_active"] = submodel.is_active

        for field in ["short_description", "long_description", 
                      "visor_type", "spoiler", "pinlock", "style"]:
            val = getattr(submodel, field, None)
            if val is not None:
                update_data[field] = val
            
        base_dir = os.path.join("qrcodes", "Submodels", submodel_id)

        if images is not None:
            new_image_urls = []
            for img in images:
                if hasattr(img, "file") and img.filename:
                    os.makedirs(base_dir, exist_ok=True)
                    ext = os.path.splitext(img.filename)[1] or ".png"
                    img_name = f"product_image_{len(new_image_urls)}{ext}"
                    img_path = os.path.join(base_dir, img_name)
                    with open(img_path, "wb") as buf:
                        shutil.copyfileobj(img.file, buf)
                    new_image_urls.append(f"/qrcodes/Submodels/{submodel_id}/{img_name}")
                elif isinstance(img, str) and img.strip():
                    new_image_urls.append(img.strip())
            update_data["product_images"] = new_image_urls



        if update_data:
            product_submodels_collection.update_one({"submodel_id": submodel_id}, {"$set": update_data})

        updated_submodel = product_submodels_collection.find_one({"submodel_id": submodel_id})

        # Propagate updated submodel fields to ALL existing variants of this submodel
        product_variants_collection.update_many(
            {"submodel_id": submodel_id},
            {"$set": {
                "short_description": updated_submodel.get("short_description"),
                "long_description": updated_submodel.get("long_description"),
                "product_images": updated_submodel.get("product_images", []),
                "visor_type": updated_submodel.get("visor_type"),
                "spoiler": updated_submodel.get("spoiler"),
                "pinlock": updated_submodel.get("pinlock"),
                "style": updated_submodel.get("style")
            }}
        )

        updated_submodel.pop("_id", None)
        
        # Resolve Model Info
        model = product_models_collection.find_one({"model_id": updated_submodel["model_id"]})
        updated_submodel["model_name"] = model.get("name") if model else None
        updated_submodel["model_status"] = model.get("is_active") if model else None
        updated_submodel["model_is_active"] = model.get("is_active") if model else None
        updated_submodel["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None
        brand = product_brands_collection.find_one({"brand_id": model.get("brand_id")}) if model else None
        updated_submodel["brand_id"] = brand.get("brand_id") if brand else None
        updated_submodel["brand_name"] = brand.get("name") if brand else None
        updated_submodel["brand_image"] = brand.get("logo_url") if brand else None
        
        # Fetch current variants
        variants_list = list(product_variants_collection.find(
            {"submodel_id": submodel_id},
            {"_id": 0, "variant_id": 1, "sku_no": 1, "size": 1, "size_name": 1, "color": 1, "product_images": 1,
             "finish": 1, "mrp": 1, "gs1_barcode": 1, "carton_barcode": 1, "is_active": 1}
        )) if submodel_id else []
        updated_submodel["variants"] = variants_list
        return updated_submodel

class ProductVariantOperations:
    @staticmethod
    def create_variants_list(submodel_id: str, parsed_variants: List[Union[list, dict]], images: List[UploadFile] = None, current_user: Optional[dict] = None):
        submodel = product_submodels_collection.find_one({"submodel_id": submodel_id})
        if not submodel:
            raise HTTPException(status_code=404, detail="Product submodel not found")

        model = product_models_collection.find_one({"model_id": submodel.get("model_id")}) if submodel else None
        brand = product_brands_collection.find_one({"brand_id": model["brand_id"]}) if model else None
        category = product_categories_collection.find_one({"category_id": model["category_id"]}) if model else None
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model["subcategory_id"]}) if model else None

        # Map uploaded files by filename
        uploaded_files = {}
        if images:
            for img in images:
                if hasattr(img, "filename") and img.filename:
                    uploaded_files[img.filename] = img

        # Check SKU uniqueness across all submodels before inserting anything
        category_id = model.get("category_id") if model else None
        for item in parsed_variants:
            if isinstance(item, dict):
                sku_no = item.get("sku_no")
                size_name = item.get("size_name")
                size = item.get("size")
            else:
                if len(item) < 3:
                    raise HTTPException(status_code=400, detail="Each variant must contain at least size_name, size, and sku_no")
                size_name = item[0]
                size = item[1]
                sku_no = item[2]

            if not sku_no or not size_name:
                raise HTTPException(status_code=400, detail="Each variant object must contain size_name and sku_no")

            resolved_size = resolve_size_from_brand(brand, category_id, size_name)
            if resolved_size is not None:
                size = resolved_size

            if size is None:
                raise HTTPException(status_code=400, detail=f"Size for size_name '{size_name}' could not be resolved from size master and was not provided.")

            if isinstance(item, dict):
                item["size"] = size
            else:
                item[1] = size

            existing_var = product_variants_collection.find_one({"sku_no": sku_no})
            if existing_var:
                raise HTTPException(status_code=400, detail=f"Product variant with SKU '{sku_no}' already exists")

        variant_ids = utils.generate_custom_ids("PVAR", product_variants_collection, "variant_id", len(parsed_variants))
        inserted_variants = []
        for idx, item in enumerate(parsed_variants):
            if isinstance(item, dict):
                size_name = item.get("size_name")
                size = item.get("size")
                sku_no = item.get("sku_no")
                variant_color = item.get("color")
                
                raw_variant_images = item.get("product_images", [])
                
                # Overrides
                gs1_barcode = item.get("gs1_barcode")
                carton_barcode = item.get("carton_barcode")
                finish = item.get("finish")
                mrp = item.get("mrp")
                style = item.get("style") if item.get("style") is not None else submodel.get("style")
                short_description = item.get("short_description") if item.get("short_description") is not None else submodel.get("short_description")
                long_description = item.get("long_description") if item.get("long_description") is not None else submodel.get("long_description")
                carton_box_size = item.get("carton_box_size")
                chinstrap_lock = item.get("chinstrap_lock") if item.get("chinstrap_lock") is not None else (model.get("chinstrap_lock") if model else None)
            else:
                size_name = item[0]
                size = item[1]
                sku_no = item[2]
                variant_color = item[3] if len(item) > 3 and item[3] is not None else None
                
                raw_variant_images = item[4] if len(item) > 4 and item[4] is not None else []
                
                # Default empty/none values
                gs1_barcode = None
                carton_barcode = None
                finish = None
                mrp = None
                style = submodel.get("style")
                short_description = submodel.get("short_description")
                long_description = submodel.get("long_description")
                carton_box_size = None
                chinstrap_lock = model.get("chinstrap_lock") if model else None
            
            variant_id = variant_ids[idx]
            
            variant_images = []
            base_dir = os.path.join("qrcodes", "Variants", variant_id)
            if raw_variant_images:
                for img_val in raw_variant_images:
                    if isinstance(img_val, str) and img_val in uploaded_files:
                        uploaded_file = uploaded_files[img_val]
                        os.makedirs(base_dir, exist_ok=True)
                        ext = os.path.splitext(uploaded_file.filename)[1] or ".png"
                        img_name = f"image_{len(variant_images)}{ext}"
                        img_path = os.path.join(base_dir, img_name)
                        uploaded_file.file.seek(0)
                        with open(img_path, "wb") as buf:
                            shutil.copyfileobj(uploaded_file.file, buf)
                        variant_images.append(f"/qrcodes/Variants/{variant_id}/{img_name}")
                    else:
                        variant_images.append(img_val)
            else:
                # Inherit from submodel directly
                variant_images = submodel.get("product_images", [])

            variant_dict = {
                "variant_id": variant_id,
                "submodel_id": submodel_id,
                "sku_no": sku_no,
                "size_name": size_name,
                "size": size,
                "is_active": True,
                "gs1_barcode": gs1_barcode,
                "carton_barcode": carton_barcode,
                "product_images": variant_images,
                "color": variant_color,
                "finish": finish,
                "mrp": mrp,
                
                "created_by": current_user["user_id"] if current_user else "SYSTEM",
                "created_at": utils.get_current_time()
            }
            product_variants_collection.insert_one(variant_dict)
            variant_dict.pop("_id", None)
            
            # Dynamic upward hierarchy resolved from pre-fetched documents
            variant_dict["short_description"] = submodel.get("short_description") if submodel else None
            variant_dict["long_description"] = submodel.get("long_description") if submodel else None
            variant_dict["visor_type"] = submodel.get("visor_type") if submodel else None
            variant_dict["spoiler"] = submodel.get("spoiler") if submodel else None
            variant_dict["pinlock"] = submodel.get("pinlock") if submodel else None
            variant_dict["style"] = submodel.get("style") if submodel else None
            variant_dict["certification"] = model.get("certification", []) if model else []
            variant_dict["chinstrap_lock"] = chinstrap_lock

            variant_dict["submodel_name"] = submodel.get("name") if submodel else None
            variant_dict["submodel_image"] = submodel.get("image") if submodel else None
            variant_dict["submodel_status"] = submodel.get("is_active") if submodel else None
            variant_dict["submodel_is_active"] = submodel.get("is_active") if submodel else None

            variant_dict["box_weight"] = model.get("box_weight") if model else None
            variant_dict["box_dimension"] = model.get("box_dimension") if model else None
            variant_dict["carton_weight"] = model.get("carton_weight") if model else None
            variant_dict["carton_dimension"] = model.get("carton_dimension") if model else None

            variant_dict["model_id"] = model.get("model_id") if model else None
            variant_dict["model_name"] = model.get("name") if model else None
            variant_dict["model_status"] = model.get("is_active") if model else None
            variant_dict["model_is_active"] = model.get("is_active") if model else None
            variant_dict["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None

            variant_dict["brand_id"] = brand.get("brand_id") if brand else None
            variant_dict["brand_name"] = brand.get("name") if brand else None
            variant_dict["brand_status"] = brand.get("is_active") if brand else None
            variant_dict["brand_is_active"] = brand.get("is_active") if brand else None

            variant_dict["category_id"] = category.get("category_id") if category else None
            variant_dict["category_name"] = category.get("name") if category else None
            variant_dict["category_status"] = category.get("is_active") if category else None
            variant_dict["category_is_active"] = category.get("is_active") if category else None

            variant_dict["subcategory_id"] = subcategory.get("subcategory_id") if subcategory else None
            variant_dict["subcategory_name"] = subcategory.get("name") if subcategory else None
            variant_dict["subcategory_status"] = subcategory.get("is_active") if subcategory else None
            variant_dict["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None

            inserted_variants.append(variant_dict)
        return {"variants": inserted_variants}

    @staticmethod
    def create_variant(variant: schemas.ProductVariantCreate, images: List[Union[UploadFile, str]] = None, certification: List[Union[UploadFile, str]] = None, current_user: Optional[dict] = None):
        if product_variants_collection.find_one({"sku_no": variant.sku_no}):
            raise HTTPException(status_code=400, detail="Product variant with this SKU number already exists")

        submodel = product_submodels_collection.find_one({"submodel_id": variant.submodel_id})
        if not submodel:
            raise HTTPException(status_code=404, detail="Product submodel not found")

        variant_dict = variant.model_dump()
        model = product_models_collection.find_one({"model_id": submodel.get("model_id")}) if submodel else None
        brand = product_brands_collection.find_one({"brand_id": model["brand_id"]}) if model else None
        category_id = model.get("category_id") if model else None

        resolved_size = resolve_size_from_brand(brand, category_id, variant.size_name)
        if resolved_size is not None:
            variant_dict["size"] = resolved_size

        if variant_dict.get("size") is None:
            raise HTTPException(status_code=400, detail=f"Size for size_name '{variant.size_name}' could not be resolved from size master and was not provided.")

        # Resolve chinstrap_lock from model if not provided on the variant
        # Note: chinstrap_lock is no longer stored on the variant DB document but resolved dynamically
        variant_id = utils.generate_custom_id("PVAR", product_variants_collection, "variant_id")
        variant_dict["variant_id"] = variant_id
        
        # Robustly handle images which might be empty strings, string urls, or UploadFiles
        image_urls = []
        base_dir = os.path.join("qrcodes", "Variants", variant_id)
        
        # Keep track of existing images or newly uploaded files
        images = images or []
        for img in images:
            if hasattr(img, "file") and img.filename:
                os.makedirs(base_dir, exist_ok=True)
                ext = os.path.splitext(img.filename)[1] or ".png"
                img_name = f"image_{len(image_urls)}{ext}"
                img_path = os.path.join(base_dir, img_name)
                with open(img_path, "wb") as buf:
                    shutil.copyfileobj(img.file, buf)
                image_urls.append(f"/qrcodes/Variants/{variant_id}/{img_name}")
            elif isinstance(img, str) and img.strip():
                # If a valid string URL/path is passed directly, keep it
                image_urls.append(img.strip())
        
        variant_dict["product_images"] = image_urls

        # Robustly handle certification files/documents which might be UploadFiles or strings
        cert_urls = []
        certification = certification or []
        for cert_item in certification:
            if hasattr(cert_item, "file") and cert_item.filename:
                os.makedirs(base_dir, exist_ok=True)
                ext = os.path.splitext(cert_item.filename)[1] or ".pdf"
                cert_name = f"cert_{len(cert_urls)}{ext}"
                cert_path = os.path.join(base_dir, cert_name)
                with open(cert_path, "wb") as buf:
                    shutil.copyfileobj(cert_item.file, buf)
                cert_urls.append(f"/qrcodes/Variants/{variant_id}/{cert_name}")
            elif isinstance(cert_item, str) and cert_item.strip():
                cert_urls.append(cert_item.strip())
        
        variant_dict["certification"] = cert_urls

        variant_dict["created_by"] = current_user["user_id"] if current_user else "SYSTEM"
        variant_dict["created_at"] = utils.get_current_time()

        # Insert raw variant data only to keep DB clean and normalize references
        product_variants_collection.insert_one(variant_dict)
        variant_dict.pop("_id", None)

        # Resolve complete upward hierarchy dynamically for the return payload
        model = product_models_collection.find_one({"model_id": submodel["model_id"]}) if submodel else None
        brand = product_brands_collection.find_one({"brand_id": model["brand_id"]}) if model else None
        category = product_categories_collection.find_one({"category_id": model["category_id"]}) if model else None
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model["subcategory_id"]}) if model else None

        variant_dict["short_description"] = submodel.get("short_description") if submodel else None
        variant_dict["long_description"] = submodel.get("long_description") if submodel else None
        variant_dict["visor_type"] = submodel.get("visor_type") if submodel else None
        variant_dict["spoiler"] = submodel.get("spoiler") if submodel else None
        variant_dict["pinlock"] = submodel.get("pinlock") if submodel else None
        variant_dict["style"] = submodel.get("style") if submodel else None
        variant_dict["certification"] = submodel.get("certification", []) if submodel else []
        variant_dict["chinstrap_lock"] = model.get("chinstrap_lock") if model else None

        variant_dict["submodel_name"] = submodel.get("name") if submodel else None
        variant_dict["submodel_image"] = submodel.get("image") if submodel else None
        variant_dict["submodel_status"] = submodel.get("is_active") if submodel else None
        variant_dict["submodel_is_active"] = submodel.get("is_active") if submodel else None

        variant_dict["box_weight"] = model.get("box_weight") if model else None
        variant_dict["box_dimension"] = model.get("box_dimension") if model else None
        variant_dict["carton_weight"] = model.get("carton_weight") if model else None
        variant_dict["carton_dimension"] = model.get("carton_dimension") if model else None

        variant_dict["model_id"] = model.get("model_id") if model else None
        variant_dict["model_name"] = model.get("name") if model else None
        variant_dict["model_status"] = model.get("is_active") if model else None
        variant_dict["model_is_active"] = model.get("is_active") if model else None
        variant_dict["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None

        variant_dict["brand_id"] = brand.get("brand_id") if brand else None
        variant_dict["brand_name"] = brand.get("name") if brand else None
        variant_dict["brand_status"] = brand.get("is_active") if brand else None
        variant_dict["brand_is_active"] = brand.get("is_active") if brand else None

        variant_dict["category_id"] = category.get("category_id") if category else None
        variant_dict["category_name"] = category.get("name") if category else None
        variant_dict["category_status"] = category.get("is_active") if category else None
        variant_dict["category_is_active"] = category.get("is_active") if category else None

        variant_dict["subcategory_id"] = subcategory.get("subcategory_id") if subcategory else None
        variant_dict["subcategory_name"] = subcategory.get("name") if subcategory else None
        variant_dict["subcategory_status"] = subcategory.get("is_active") if subcategory else None
        variant_dict["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None

        return variant_dict

    @staticmethod
    def get_variants(submodel_id: Optional[str] = None, page: int = 1, limit: int = 50, search: str = "", model_id: Optional[str] = None, brand_id: Optional[str] = None, is_active: Optional[bool] = None):
        query = {}
        model_query = {}
        if brand_id:
            model_query["brand_id"] = brand_id
        if model_id:
            model_query["model_id"] = model_id
            
        if model_query:
            allowed_models = [m["model_id"] for m in product_models_collection.find(model_query)]
            allowed_submodels = [sm["submodel_id"] for sm in product_submodels_collection.find({"model_id": {"$in": allowed_models}})]
            
            if submodel_id:
                if submodel_id in allowed_submodels:
                    query["submodel_id"] = submodel_id
                else:
                    query["submodel_id"] = "NON_EXISTENT_SUBMODEL"
            else:
                query["submodel_id"] = {"$in": allowed_submodels}
        else:
            if submodel_id:
                query["submodel_id"] = submodel_id
                
        if is_active is not None:
            query["is_active"] = is_active
            
        if search:
            query["$or"] = [
                {"sku_no": {"$regex": search, "$options": "i"}},
                {"variant_id": {"$regex": search, "$options": "i"}},
                {"color": {"$regex": search, "$options": "i"}},
                {"size_name": {"$regex": search, "$options": "i"}}
            ]
        total_count = product_variants_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        variants = list(product_variants_collection.find(query).skip(skip).limit(limit))
        
        # Prefetch referenced collections to avoid N+1 query overhead
        categories_by_id = {c["category_id"]: c for c in product_categories_collection.find()}
        subcategories_by_id = {s["subcategory_id"]: s for s in product_subcategories_collection.find()}
        brands_by_id = {b["brand_id"]: b for b in product_brands_collection.find()}
        models_by_id = {m["model_id"]: m for m in product_models_collection.find()}
        submodels_by_id = {sm["submodel_id"]: sm for sm in product_submodels_collection.find()}

        for v in variants:
            v.pop("_id", None)
            
            # Resolve complete upward hierarchy dynamically at query time
            submodel = submodels_by_id.get(v["submodel_id"])
            model = models_by_id.get(submodel["model_id"]) if submodel else None
            brand = brands_by_id.get(model["brand_id"]) if model else None
            category = categories_by_id.get(model["category_id"]) if model else None
            subcategory = subcategories_by_id.get(model["subcategory_id"]) if model else None

            v["submodel_name"] = submodel.get("name") if submodel else None
            v["submodel_image"] = submodel.get("image") if submodel else None
            v["submodel_status"] = submodel.get("is_active") if submodel else None
            v["submodel_is_active"] = submodel.get("is_active") if submodel else None

            v["box_weight"] = model.get("box_weight") if model else None
            v["box_dimension"] = model.get("box_dimension") if model else None
            v["carton_weight"] = model.get("carton_weight") if model else None
            v["carton_dimension"] = model.get("carton_dimension") if model else None

            v["model_id"] = model.get("model_id") if model else None
            v["model_name"] = model.get("name") if model else None
            v["model_status"] = model.get("is_active") if model else None
            v["model_is_active"] = model.get("is_active") if model else None
            v["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None

            # Separate submodel images from variant images
            model_images = submodel.get("product_images") or []
            v["model_images"] = model_images
            
            variant_images = v.get("product_images") or []
            v["product_images"] = [img for img in variant_images if img not in model_images]

            # Dynamic submodel/model resolutions
            v["short_description"] = submodel.get("short_description") if submodel else None
            v["long_description"] = submodel.get("long_description") if submodel else None
            v["visor_type"] = submodel.get("visor_type") if submodel else None
            v["spoiler"] = submodel.get("spoiler") if submodel else None
            v["pinlock"] = submodel.get("pinlock") if submodel else None
            v["style"] = submodel.get("style") if submodel else None
            v["certification"] = model.get("certification", []) if model else []
            v["chinstrap_lock"] = v.get("chinstrap_lock") or (model.get("chinstrap_lock") if model else None)

            v["brand_id"] = brand.get("brand_id") if brand else None
            v["brand_name"] = brand.get("name") if brand else None
            v["brand_status"] = brand.get("is_active") if brand else None
            v["brand_is_active"] = brand.get("is_active") if brand else None
            v["brand_image"] = brand.get("logo_url") if brand else None

            v["category_id"] = category.get("category_id") if category else None
            v["category_name"] = category.get("name") if category else None
            v["category_status"] = category.get("is_active") if category else None
            v["category_is_active"] = category.get("is_active") if category else None

            v["subcategory_id"] = subcategory.get("subcategory_id") if subcategory else None
            v["subcategory_name"] = subcategory.get("name") if subcategory else None
            v["subcategory_status"] = subcategory.get("is_active") if subcategory else None
            v["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None
        return {
            "variants": variants,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_variant(variant_id: str, variant: schemas.ProductVariantUpdate, images: List[Union[UploadFile, str]] = None, certification: List[Union[UploadFile, str]] = None):
        existing = product_variants_collection.find_one({"variant_id": variant_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product variant not found")

        update_data = variant.model_dump(exclude_unset=True)
        
        # Robustly handle images which might be empty strings, string urls, or UploadFiles
        image_urls = existing.get("product_images") or []
        base_dir = os.path.join("qrcodes", "Variants", variant_id)
        has_new_uploads = False

        if images:
            for img in images:
                if hasattr(img, "file") and img.filename:
                    has_new_uploads = True
                    os.makedirs(base_dir, exist_ok=True)
                    ext = os.path.splitext(img.filename)[1] or ".png"
                    img_name = f"image_{len(image_urls)}{ext}"
                    img_path = os.path.join(base_dir, img_name)
                    with open(img_path, "wb") as buf:
                        shutil.copyfileobj(img.file, buf)
                    image_urls.append(f"/qrcodes/Variants/{variant_id}/{img_name}")
                elif isinstance(img, str) and img.strip():
                    # If string values are passed, ensure they are kept
                    has_new_uploads = True
                    if img.strip() not in image_urls:
                        image_urls.append(img.strip())

        if has_new_uploads:
            update_data["product_images"] = image_urls

        if update_data:
            product_variants_collection.update_one({"variant_id": variant_id}, {"$set": update_data})

        updated = product_variants_collection.find_one({"variant_id": variant_id})
        updated.pop("_id", None)

        # Resolve complete upward hierarchy dynamically at update time
        submodel = product_submodels_collection.find_one({"submodel_id": updated["submodel_id"]})
        model = product_models_collection.find_one({"model_id": submodel["model_id"]}) if submodel else None
        brand = product_brands_collection.find_one({"brand_id": model["brand_id"]}) if model else None
        category = product_categories_collection.find_one({"category_id": model["category_id"]}) if model else None
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model["subcategory_id"]}) if model else None

        updated["submodel_name"] = submodel.get("name") if submodel else None
        updated["submodel_image"] = submodel.get("image") if submodel else None
        updated["submodel_status"] = submodel.get("is_active") if submodel else None
        updated["submodel_is_active"] = submodel.get("is_active") if submodel else None

        updated["box_weight"] = model.get("box_weight") if model else None
        updated["box_dimension"] = model.get("box_dimension") if model else None
        updated["carton_weight"] = model.get("carton_weight") if model else None
        updated["carton_dimension"] = model.get("carton_dimension") if model else None

        updated["model_id"] = model.get("model_id") if model else None
        updated["model_name"] = model.get("name") if model else None
        updated["model_status"] = model.get("is_active") if model else None
        updated["model_is_active"] = model.get("is_active") if model else None
        updated["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None

        # Dynamic submodel/model resolutions
        updated["short_description"] = submodel.get("short_description") if submodel else None
        updated["long_description"] = submodel.get("long_description") if submodel else None
        updated["visor_type"] = submodel.get("visor_type") if submodel else None
        updated["spoiler"] = submodel.get("spoiler") if submodel else None
        updated["pinlock"] = submodel.get("pinlock") if submodel else None
        updated["style"] = submodel.get("style") if submodel else None
        updated["certification"] = model.get("certification", []) if model else []
        updated["chinstrap_lock"] = updated.get("chinstrap_lock") or (model.get("chinstrap_lock") if model else None)

        updated["brand_id"] = brand.get("brand_id") if brand else None
        updated["brand_name"] = brand.get("name") if brand else None
        updated["brand_status"] = brand.get("is_active") if brand else None
        updated["brand_is_active"] = brand.get("is_active") if brand else None
        updated["brand_image"] = brand.get("logo_url") if brand else None

        updated["category_id"] = category.get("category_id") if category else None
        updated["category_name"] = category.get("name") if category else None
        updated["category_status"] = category.get("is_active") if category else None
        updated["category_is_active"] = category.get("is_active") if category else None

        updated["subcategory_id"] = subcategory.get("subcategory_id") if subcategory else None
        updated["subcategory_name"] = subcategory.get("name") if subcategory else None
        updated["subcategory_status"] = subcategory.get("is_active") if subcategory else None
        updated["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None
        return updated

    @staticmethod
    def filter_variants(
        category_id: Optional[str] = None,
        subcategory_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        model_id: Optional[str] = None,
        submodel_id: Optional[str] = None,
        color: Optional[str] = None,
        size: Optional[int] = None,
        finish: Optional[str] = None,
        visor_type: Optional[str] = None,
        spoiler: Optional[str] = None,
        certification: Optional[str] = None,
        chinstrap_lock: Optional[str] = None,
        pinlock: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ):
        submodel_query = {}
        if submodel_id:
            submodel_query["submodel_id"] = submodel_id
        if model_id:
            submodel_query["model_id"] = model_id

        if brand_id or category_id or subcategory_id:
            model_query = {}
            if brand_id:
                model_query["brand_id"] = brand_id
            if category_id:
                model_query["category_id"] = category_id
            if subcategory_id:
                model_query["subcategory_id"] = subcategory_id
            
            matching_models = list(product_models_collection.find(model_query))
            if not matching_models:
                return []
            matching_model_ids = [m["model_id"] for m in matching_models]
            
            if "model_id" in submodel_query:
                if submodel_query["model_id"] not in matching_model_ids:
                    return []
            else:
                submodel_query["model_id"] = {"$in": matching_model_ids}

        if submodel_query or brand_id or category_id or subcategory_id or model_id:
            matching_submodels = list(product_submodels_collection.find(submodel_query))
            if not matching_submodels:
                return []
            matching_submodel_ids = [s["submodel_id"] for s in matching_submodels]
        else:
            matching_submodel_ids = None

        variant_query = {}
        if matching_submodel_ids is not None:
            variant_query["submodel_id"] = {"$in": matching_submodel_ids}
        
        if color:
            variant_query["color"] = {"$regex": f"^{color}$", "$options": "i"}
        if size is not None:
            variant_query["size"] = size
        if finish:
            variant_query["finish"] = {"$regex": f"^{finish}$", "$options": "i"}
        if visor_type:
            variant_query["visor_type"] = {"$regex": f"^{visor_type}$", "$options": "i"}
        if spoiler:
            variant_query["spoiler"] = {"$regex": f"^{spoiler}$", "$options": "i"}
        if certification:
            variant_query["certification"] = {"$regex": f"^{certification}$", "$options": "i"}
        if chinstrap_lock:
            variant_query["chinstrap_lock"] = {"$regex": f"^{chinstrap_lock}$", "$options": "i"}
        if pinlock:
            variant_query["pinlock"] = {"$regex": f"^{pinlock}$", "$options": "i"}
        if is_active is not None:
            variant_query["is_active"] = is_active
        
        if search:
            search_regex = {"$regex": search, "$options": "i"}
            variant_query["$or"] = [
                {"sku_no": search_regex},
                {"short_description": search_regex},
                {"long_description": search_regex}
            ]

        variants = list(product_variants_collection.find(variant_query))
        
        # Prefetch referenced collections to avoid N+1 query overhead
        categories_by_id = {c["category_id"]: c for c in product_categories_collection.find()}
        subcategories_by_id = {s["subcategory_id"]: s for s in product_subcategories_collection.find()}
        brands_by_id = {b["brand_id"]: b for b in product_brands_collection.find()}
        models_by_id = {m["model_id"]: m for m in product_models_collection.find()}
        submodels_by_id = {sm["submodel_id"]: sm for sm in product_submodels_collection.find()}

        for v in variants:
            v.pop("_id", None)
            
            submodel = submodels_by_id.get(v["submodel_id"])
            model = models_by_id.get(submodel["model_id"]) if submodel else None
            brand = brands_by_id.get(model["brand_id"]) if model else None
            category = categories_by_id.get(model["category_id"]) if model else None
            subcategory = subcategories_by_id.get(model["subcategory_id"]) if model else None

            v["submodel_name"] = submodel.get("name") if submodel else None
            v["submodel_image"] = submodel.get("image") if submodel else None
            v["submodel_status"] = submodel.get("is_active") if submodel else None
            v["submodel_is_active"] = submodel.get("is_active") if submodel else None

            v["box_weight"] = model.get("box_weight") if model else None
            v["box_dimension"] = model.get("box_dimension") if model else None
            v["carton_weight"] = model.get("carton_weight") if model else None
            v["carton_dimension"] = model.get("carton_dimension") if model else None

            v["model_id"] = model.get("model_id") if model else None
            v["model_name"] = model.get("name") if model else None
            v["model_status"] = model.get("is_active") if model else None
            v["model_is_active"] = model.get("is_active") if model else None
            v["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None

            # Dynamic submodel/model resolutions
            v["short_description"] = submodel.get("short_description") if submodel else None
            v["long_description"] = submodel.get("long_description") if submodel else None
            v["visor_type"] = submodel.get("visor_type") if submodel else None
            v["spoiler"] = submodel.get("spoiler") if submodel else None
            v["pinlock"] = submodel.get("pinlock") if submodel else None
            v["style"] = submodel.get("style") if submodel else None
            v["certification"] = model.get("certification", []) if model else []
            v["chinstrap_lock"] = v.get("chinstrap_lock") or (model.get("chinstrap_lock") if model else None)

            v["brand_id"] = brand.get("brand_id") if brand else None
            v["brand_name"] = brand.get("name") if brand else None
            v["brand_status"] = brand.get("is_active") if brand else None
            v["brand_is_active"] = brand.get("is_active") if brand else None
            v["brand_image"] = brand.get("logo_url") if brand else None

            v["category_id"] = category.get("category_id") if category else None
            v["category_name"] = category.get("name") if category else None
            v["category_status"] = category.get("is_active") if category else None
            v["category_is_active"] = category.get("is_active") if category else None

            v["subcategory_name"] = subcategory.get("name") if subcategory else None
            v["subcategory_status"] = subcategory.get("is_active") if subcategory else None
            v["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None
        return variants

    @staticmethod
    def get_variant_detail(variant_id: str):
        variant = product_variants_collection.find_one({"variant_id": variant_id})
        if not variant:
            raise HTTPException(status_code=404, detail="Product variant not found")
        
        variant.pop("_id", None)

        # Resolve complete upward hierarchy dynamically
        submodel = product_submodels_collection.find_one({"submodel_id": variant["submodel_id"]})
        model = product_models_collection.find_one({"model_id": submodel["model_id"]}) if submodel else None
        brand = product_brands_collection.find_one({"brand_id": model["brand_id"]}) if model else None
        category = product_categories_collection.find_one({"category_id": model["category_id"]}) if model else None
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model["subcategory_id"]}) if model else None

        variant["submodel_name"] = submodel.get("name") if submodel else None
        variant["submodel_image"] = submodel.get("image") if submodel else None
        variant["submodel_status"] = submodel.get("is_active") if submodel else None
        variant["submodel_is_active"] = submodel.get("is_active") if submodel else None

        variant["box_weight"] = model.get("box_weight") if model else None
        variant["box_dimension"] = model.get("box_dimension") if model else None
        variant["carton_weight"] = model.get("carton_weight") if model else None
        variant["carton_dimension"] = model.get("carton_dimension") if model else None

        variant["model_id"] = model.get("model_id") if model else None
        variant["model_name"] = model.get("name") if model else None
        variant["model_status"] = model.get("is_active") if model else None
        variant["model_is_active"] = model.get("is_active") if model else None
        variant["model_chinstrap_lock"] = model.get("chinstrap_lock") if model else None
        
        # Separate submodel images from variant images
        model_images = submodel.get("product_images") or [] if submodel else []
        variant["model_images"] = model_images
        
        variant_images = variant.get("product_images") or []
        variant["product_images"] = [img for img in variant_images if img not in model_images]

        # Dynamic submodel/model resolutions
        variant["short_description"] = submodel.get("short_description") if submodel else None
        variant["long_description"] = submodel.get("long_description") if submodel else None
        variant["visor_type"] = submodel.get("visor_type") if submodel else None
        variant["spoiler"] = submodel.get("spoiler") if submodel else None
        variant["pinlock"] = submodel.get("pinlock") if submodel else None
        variant["style"] = submodel.get("style") if submodel else None
        variant["certification"] = model.get("certification", []) if model else []
        variant["chinstrap_lock"] = variant.get("chinstrap_lock") or (model.get("chinstrap_lock") if model else None)

        variant["brand_id"] = brand.get("brand_id") if brand else None
        variant["brand_name"] = brand.get("name") if brand else None
        variant["brand_status"] = brand.get("is_active") if brand else None
        variant["brand_is_active"] = brand.get("is_active") if brand else None
        variant["brand_image"] = brand.get("logo_url") if brand else None

        variant["category_id"] = category.get("category_id") if category else None
        variant["category_name"] = category.get("name") if category else None
        variant["category_status"] = category.get("is_active") if category else None
        variant["category_is_active"] = category.get("is_active") if category else None

        variant["subcategory_id"] = subcategory.get("subcategory_id") if subcategory else None
        variant["subcategory_name"] = subcategory.get("name") if subcategory else None
        variant["subcategory_status"] = subcategory.get("is_active") if subcategory else None
        variant["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None

        # Resolve sister variants under the same submodel
        sister_variants = []
        if submodel:
            # Find all variants sharing the same submodel_id, excluding the current one
            sisters_cursor = product_variants_collection.find({
                "submodel_id": variant["submodel_id"],
                "variant_id": {"$ne": variant_id}
            })
            for s in sisters_cursor:
                sister_variants.append({
                    "variant_id": s["variant_id"],
                    "sku_no": s["sku_no"],
                    "size": s.get("size"),
                    "size_name": s.get("size_name"),
                    "color": s.get("color"),
                    "finish": s.get("finish"),
                    "is_active": s.get("is_active")
                })
        
        variant["sister_variants"] = sister_variants
        return variant



# Categories
@router.post("/categories/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_product_category(
    category: schemas.ProductCategoryCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductCategoryOperations.create_category(category, current_user)

@router.get("/categories/", response_model=dict)
def get_product_categories(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query("")
):
    return ProductCategoryOperations.get_categories(page=page, limit=limit, search=search)

@router.put("/categories/{category_id}", response_model=dict)
def update_product_category(
    category_id: str,
    category: schemas.ProductCategoryUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductCategoryOperations.update_category(category_id, category)

# Subcategories
@router.post("/subcategories/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_product_subcategory(
    subcategory: schemas.ProductSubCategoryCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductSubCategoryOperations.create_subcategory(subcategory, current_user)

@router.get("/subcategories/", response_model=dict)
def get_product_subcategories(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query("")
):
    return ProductSubCategoryOperations.get_subcategories(page=page, limit=limit, search=search)

@router.put("/subcategories/{subcategory_id}", response_model=dict)
def update_product_subcategory(
    subcategory_id: str,
    subcategory: schemas.ProductSubCategoryUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductSubCategoryOperations.update_subcategory(subcategory_id, subcategory)

# Brands
@router.post("/brands/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_product_brand(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    is_active: bool = Form(True),
    size_master: Optional[str] = Form(None),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductBrandOperations.create_brand(name, description, logo, is_active, size_master, current_user)

@router.get("/brands/", response_model=dict)
def get_product_brands(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query("")
):
    return ProductBrandOperations.get_brands(page=page, limit=limit, search=search)

@router.put("/brands/{brand_id}", response_model=dict)
def update_product_brand(
    brand_id: str,
    brand: schemas.ProductBrandUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductBrandOperations.update_brand(brand_id, brand)

# Models
@router.post("/models/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_product_model(
    model: schemas.ProductModelCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductModelOperations.create_model(model, current_user)

@router.get("/models/", response_model=dict)
def get_product_models(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    brand_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None)
):
    return ProductModelOperations.get_models(page=page, limit=limit, search=search, brand_id=brand_id, is_active=is_active)

@router.put("/models/{model_id}", response_model=dict)
def update_product_model(
    model_id: str,
    model: schemas.ProductModelUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductModelOperations.update_model(model_id, model)

# Submodels
@router.post("/submodels/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_product_submodel(
    name: str = Form(...),
    model_id: str = Form(...),
    is_active: bool = Form(True),
    
    # Variant fields at submodel level
    short_description: Optional[str] = Form(None),
    long_description: Optional[str] = Form(None),
    visor_type: Optional[str] = Form(None),
    spoiler: Optional[str] = Form(None),
    pinlock: Optional[str] = Form(None),
    images: list[UploadFile] = File(default=[]),
    style: Optional[str] = Form(None),
    
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    valid_images = []
    if isinstance(images, list):
        valid_images = [img for img in images if hasattr(img, "file") and getattr(img, "filename", None)]
    elif hasattr(images, "file") and getattr(images, "filename", None):
        valid_images = [images]


    submodel_schema = schemas.ProductSubModelCreate(
        name=name,
        model_id=model_id,
        is_active=is_active,
        short_description=short_description,
        long_description=long_description,
        product_images=[],
        visor_type=visor_type,
        spoiler=spoiler,
        pinlock=pinlock,
        style=style
    )
    return ProductSubModelOperations.create_submodel(
        submodel=submodel_schema, images=valid_images, current_user=current_user
    )

@router.get("/submodels/", response_model=dict)
def get_product_submodels(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    model_id: Optional[str] = Query(None),
    brand_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None)
):
    return ProductSubModelOperations.get_submodels(page=page, limit=limit, search=search, model_id=model_id, brand_id=brand_id, is_active=is_active)

@router.put("/submodels/{submodel_id}", response_model=dict)
def update_product_submodel(
    submodel_id: str,
    name: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    
    # New variant fields at submodel level
    short_description: Optional[str] = Form(None),
    long_description: Optional[str] = Form(None),
    visor_type: Optional[str] = Form(None),
    spoiler: Optional[str] = Form(None),
    pinlock: Optional[str] = Form(None),
    images: Optional[list[UploadFile]] = File(default=None),
    style: Optional[str] = Form(None),
    
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    valid_images = None
    if images is not None:
        valid_images = []
        if isinstance(images, list):
            valid_images = [img for img in images if hasattr(img, "file") and getattr(img, "filename", None)]
        elif hasattr(images, "file") and getattr(images, "filename", None):
            valid_images = [images]



    submodel_schema = schemas.ProductSubModelUpdate(
        is_active=is_active,
        
        # New variant fields stored on submodel
        short_description=short_description,
        long_description=long_description,
        product_images=None,
        visor_type=visor_type,
        spoiler=spoiler,
        pinlock=pinlock,
        style=style
    )
    return ProductSubModelOperations.update_submodel(
        submodel_id=submodel_id,
        submodel=submodel_schema,
        name=name,
        images=valid_images,
        current_user=current_user
    )



@router.post("/variants/", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_product_variants(
    submodel_id: str = Form(...),
    variants: str = Form(...),
    images: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    import json
    try:
        parsed_variants = json.loads(variants)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid format for variants. Must be a JSON array of lists or objects.")
    
    if not isinstance(parsed_variants, list) or not all(
        (isinstance(v, list) and 3 <= len(v) <= 5) or
        (isinstance(v, dict) and "sku_no" in v and "size_name" in v and "size" in v)
        for v in parsed_variants
    ):
        raise HTTPException(status_code=400, detail="Variants must be a list of lists of length 3 to 5 (e.g. [size_name, size, sku_no, color, product_images]) or objects containing 'sku_no', 'size_name', and 'size'.")

    valid_images = []
    if isinstance(images, list):
        valid_images = [img for img in images if hasattr(img, "file") and getattr(img, "filename", None)]
    elif hasattr(images, "file") and getattr(images, "filename", None):
        valid_images = [images]

    return ProductVariantOperations.create_variants_list(submodel_id, parsed_variants, valid_images, current_user)

@router.put("/variants/{variant_id}", response_model=dict)
def update_product_variant(
    variant_id: str,
    is_active: Optional[bool] = Form(None),
    mrp: Optional[str] = Form(None),
    carton_barcode: Optional[str] = Form(None),
    gs1_barcode: Optional[str] = Form(None),
    size: Optional[int] = Form(None),
    size_name: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    finish: Optional[str] = Form(None),
    images: Optional[list[UploadFile]] = File(default=None),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    parsed_mrp = None
    if mrp is not None:
        mrp_str = str(mrp).strip()
        if mrp_str.startswith("{") and mrp_str.endswith("}"):
            import json
            try:
                parsed_mrp = json.loads(mrp_str)
            except Exception:
                parsed_mrp = {"INR": float(mrp_str)}
        else:
            try:
                parsed_mrp = {"INR": float(mrp_str)}
            except Exception:
                parsed_mrp = None

    valid_images = None
    if images is not None:
        valid_images = []
        if isinstance(images, list):
            valid_images = [img for img in images if hasattr(img, "file") and getattr(img, "filename", None)]
        elif hasattr(images, "file") and getattr(images, "filename", None):
            valid_images = [images]

    update_schema = schemas.ProductVariantUpdate(
        is_active=is_active,
        gs1_barcode=gs1_barcode,
        carton_barcode=carton_barcode,
        color=color,
        size_name=size_name,
        size=size,
        finish=finish,
        product_images=None,
        mrp=parsed_mrp
    )

    return ProductVariantOperations.update_variant(variant_id, update_schema, valid_images)

@router.get("/variants/", response_model=dict)
def get_product_variants(
    submodel_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    model_id: Optional[str] = Query(None),
    brand_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None)
):
    return ProductVariantOperations.get_variants(submodel_id, page=page, limit=limit, search=search, model_id=model_id, brand_id=brand_id, is_active=is_active)

@router.get("/variants/filter/", response_model=List[dict])
def filter_product_variants(
    category_id: Optional[str] = None,
    subcategory_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    model_id: Optional[str] = None,
    submodel_id: Optional[str] = None,
    color: Optional[str] = None,
    size: Optional[int] = None,
    finish: Optional[str] = None,
    visor_type: Optional[str] = None,
    spoiler: Optional[str] = None,
    certification: Optional[str] = None,
    chinstrap_lock: Optional[str] = None,
    pinlock: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
):
    return ProductVariantOperations.filter_variants(
        category_id=category_id,
        subcategory_id=subcategory_id,
        brand_id=brand_id,
        model_id=model_id,
        submodel_id=submodel_id,
        color=color,
        size=size,
        finish=finish,
        visor_type=visor_type,
        spoiler=spoiler,
        certification=certification,
        chinstrap_lock=chinstrap_lock,
        pinlock=pinlock,
        is_active=is_active,
        search=search
    )


@router.get("/variants/{variant_id}", response_model=dict)
def get_product_variant(variant_id: str):
    return ProductVariantOperations.get_variant_detail(variant_id)


@router.get("/models/{model_id}", response_model=dict)
def get_product_model(model_id: str):
    doc = product_models_collection.find_one({"model_id": model_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Model not found")
    doc.pop("_id", None)
    brand = product_brands_collection.find_one({"brand_id": doc.get("brand_id")}) if doc.get("brand_id") else None
    category = product_categories_collection.find_one({"category_id": doc.get("category_id")}) if doc.get("category_id") else None
    subcategory = product_subcategories_collection.find_one({"subcategory_id": doc.get("subcategory_id")}) if doc.get("subcategory_id") else None
    doc["brand_name"] = brand.get("name") if brand else None
    doc["brand_image"] = brand.get("logo_url") if brand else None
    doc["category_name"] = category.get("name") if category else None
    doc["subcategory_name"] = subcategory.get("name") if subcategory else None
    return doc


@router.get("/submodels/{submodel_id}", response_model=dict)
def get_product_submodel(submodel_id: str):
    doc = product_submodels_collection.find_one({"submodel_id": submodel_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Submodel not found")
    doc.pop("_id", None)
    model = product_models_collection.find_one({"model_id": doc.get("model_id")}) if doc.get("model_id") else None
    brand = product_brands_collection.find_one({"brand_id": model.get("brand_id")}) if model else None
    category = product_categories_collection.find_one({"category_id": model.get("category_id")}) if model else None
    subcategory = product_subcategories_collection.find_one({"subcategory_id": model.get("subcategory_id")}) if model else None
    doc["model_name"] = model.get("name") if model else None
    doc["model_is_active"] = model.get("is_active") if model else None
    doc["brand_id"] = brand.get("brand_id") if brand else None
    doc["brand_name"] = brand.get("name") if brand else None
    doc["brand_image"] = brand.get("logo_url") if brand else None
    doc["category_id"] = category.get("category_id") if category else None
    doc["category_name"] = category.get("name") if category else None
    doc["subcategory_id"] = subcategory.get("subcategory_id") if subcategory else None
    doc["subcategory_name"] = subcategory.get("name") if subcategory else None
    return doc
