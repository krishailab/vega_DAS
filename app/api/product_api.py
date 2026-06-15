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

        brand_dict = {
            "brand_id": brand_id,
            "name": name,
            "description": description,
            "logo_url": logo_url,
            "is_active": is_active,
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
        is_active: Optional[bool]
    ):
        existing = product_brands_collection.find_one({"brand_id": brand_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Product brand not found")

        update_data = {}
        if is_active is not None:
            update_data["is_active"] = is_active

        if update_data:
            product_brands_collection.update_one({"brand_id": brand_id}, {"$set": update_data})

        updated = product_brands_collection.find_one({"brand_id": brand_id})
        updated.pop("_id", None)
        return updated

class ProductModelOperations:
    @staticmethod
    def create_model(model: schemas.ProductModelCreate, current_user: dict):
        # Validate parent category
        category = product_categories_collection.find_one({"category_id": model.category_id})
        if not category:
            raise HTTPException(status_code=404, detail="Product category not found")

        # Validate parent subcategory
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model.subcategory_id})
        if not subcategory:
            raise HTTPException(status_code=404, detail="Product subcategory not found")

        # Validate parent brand
        brand = product_brands_collection.find_one({"brand_id": model.brand_id})
        if not brand:
            raise HTTPException(status_code=404, detail="Product brand not found")

        if product_models_collection.find_one({
            "name": model.name,
            "brand_id": model.brand_id,
            "category_id": model.category_id,
            "subcategory_id": model.subcategory_id
        }):
            raise HTTPException(status_code=400, detail="Product model already exists with these parameters")

        model_dict = model.model_dump()
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
    def get_models(page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"model_id": {"$regex": search, "$options": "i"}},
                {"brand_name": {"$regex": search, "$options": "i"}},
                {"category_name": {"$regex": search, "$options": "i"}},
                {"subcategory_name": {"$regex": search, "$options": "i"}}
            ]
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
        image_file: Optional[UploadFile], 
        images: List[Union[UploadFile, str]], 
        certification: List[Union[UploadFile, str]], 
        parsed_variants: List[list],
        current_user: dict
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
        
        image_url = None
        if image_file and image_file.filename:
            os.makedirs(base_dir, exist_ok=True)
            ext = os.path.splitext(image_file.filename)[1] or ".png"
            image_path = os.path.join(base_dir, f"image{ext}")
            with open(image_path, "wb") as buf:
                shutil.copyfileobj(image_file.file, buf)
            image_url = f"/qrcodes/Submodels/{submodel_id}/image{ext}"
        elif submodel.image:
            image_url = submodel.image

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

        # Save certification
        cert_urls = []
        for cert_item in certification:
            if hasattr(cert_item, "file") and cert_item.filename:
                os.makedirs(base_dir, exist_ok=True)
                ext = os.path.splitext(cert_item.filename)[1] or ".pdf"
                cert_name = f"cert_{len(cert_urls)}{ext}"
                cert_path = os.path.join(base_dir, cert_name)
                with open(cert_path, "wb") as buf:
                    shutil.copyfileobj(cert_item.file, buf)
                cert_urls.append(f"/qrcodes/Submodels/{submodel_id}/{cert_name}")
            elif isinstance(cert_item, str) and cert_item.strip():
                cert_urls.append(cert_item.strip())

        submodel_dict = {
            "submodel_id": submodel_id,
            "name": submodel.name,
            "model_id": submodel.model_id,
            "image": image_url,
            "is_active": submodel.is_active,
            "box_weight": submodel.box_weight,
            "box_dimension": submodel.box_dimension,
            "carton_weight": submodel.carton_weight,
            "carton_dimension": submodel.carton_dimension,
            
            # Variant fields stored on submodel
            "gs1_barcode": submodel.gs1_barcode,
            "short_description": submodel.short_description,
            "long_description": submodel.long_description,
            "carton_box_size": submodel.carton_box_size,
            "carton_barcode": submodel.carton_barcode,
            "product_images": product_image_urls,
            "finish": submodel.finish,
            "certification": cert_urls,
            "visor_type": submodel.visor_type,
            "spoiler": submodel.spoiler,
            "chinstrap_lock": submodel.chinstrap_lock,
            "pinlock": submodel.pinlock,
            "mrp": submodel.mrp,
            
            "model_name": model.get("name"),
            "model_status": model.get("is_active"),
            "model_is_active": model.get("is_active"),
            "brand_id": (product_brands_collection.find_one({"brand_id": model.get("brand_id")}) or {}).get("brand_id") if model else None,
            "brand_name": (product_brands_collection.find_one({"brand_id": model.get("brand_id")}) or {}).get("name") if model else None,
            "created_by": current_user["user_id"],
            "created_at": utils.get_current_time()
        }

        # Check SKU uniqueness across all submodels before inserting anything
        for item in parsed_variants:
            sku_no = item[2]
            existing_var = product_variants_collection.find_one({"sku_no": sku_no})
            if existing_var:
                raise HTTPException(status_code=400, detail=f"Product variant with SKU '{sku_no}' already exists")

        product_submodels_collection.insert_one(submodel_dict)
        submodel_dict.pop("_id", None)

        inserted_variants = []
        for item in parsed_variants:
            size_name = item[0]
            size = item[1]
            sku_no = item[2]
            variant_color = item[3] if len(item) > 3 and item[3] is not None else None
            variant_images = item[4] if len(item) > 4 and item[4] is not None else product_image_urls
            
            variant_id = utils.generate_custom_id("PVAR", product_variants_collection, "variant_id")
            variant_dict = {
                "variant_id": variant_id,
                "submodel_id": submodel_id,
                "sku_no": sku_no,
                "size_name": size_name,
                "size": size,
                "is_active": True,
                
                # Propagate submodel fields to variant
                "gs1_barcode": submodel.gs1_barcode,
                "short_description": submodel.short_description,
                "long_description": submodel.long_description,
                "carton_box_size": submodel.carton_box_size,
                "carton_barcode": submodel.carton_barcode,
                "product_images": variant_images,
                "color": variant_color,
                "finish": submodel.finish,
                "certification": cert_urls,
                "visor_type": submodel.visor_type,
                "spoiler": submodel.spoiler,
                "chinstrap_lock": submodel.chinstrap_lock,
                "pinlock": submodel.pinlock,
                "mrp": submodel.mrp,
                
                "created_by": current_user["user_id"],
                "created_at": utils.get_current_time()
            }
            product_variants_collection.insert_one(variant_dict)
            inserted_variants.append({
                "variant_id": variant_dict["variant_id"],
                "sku_no": variant_dict["sku_no"],
                "size": variant_dict["size"],
                "size_name": variant_dict["size_name"],
                "color": variant_dict.get("color"),
                "product_images": variant_dict.get("product_images", [])
            })
            
        submodel_dict["variants"] = inserted_variants
        return submodel_dict

    @staticmethod
    def get_submodels(page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"submodel_id": {"$regex": search, "$options": "i"}},
                {"model_name": {"$regex": search, "$options": "i"}},
                {"brand_name": {"$regex": search, "$options": "i"}}
            ]
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
            {"_id": 0, "variant_id": 1, "sku_no": 1, "size": 1, "size_name": 1, "color": 1, "product_images": 1, "submodel_id": 1}
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
                "product_images": v.get("product_images", [])
            })
            
        for s in submodels:
            s.pop("_id", None)
            # Resolve Model Info
            model = models_dict.get(s.get("model_id"))
            s["model_name"] = model.get("name") if model else None
            s["model_status"] = model.get("is_active") if model else None
            s["model_is_active"] = model.get("is_active") if model else None
            
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
        certification: Optional[List[Union[UploadFile, str]]] = None,
        parsed_variants: Optional[List[list]] = None,
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

        for field in ["box_weight", "box_dimension", "carton_weight", "carton_dimension",
                      "gs1_barcode", "short_description", "long_description", "carton_box_size", "carton_barcode", "finish", 
                      "visor_type", "spoiler", "chinstrap_lock", "pinlock", "mrp"]:
            val = getattr(submodel, field, None)
            if val is not None:
                update_data[field] = val
            
        base_dir = os.path.join("qrcodes", "Submodels", submodel_id)
        if image_file and image_file.filename:
            os.makedirs(base_dir, exist_ok=True)
            ext = os.path.splitext(image_file.filename)[1] or ".png"
            image_path = os.path.join(base_dir, f"image{ext}")
            with open(image_path, "wb") as buf:
                shutil.copyfileobj(image_file.file, buf)
            update_data["image"] = f"/qrcodes/Submodels/{submodel_id}/image{ext}"
        elif submodel.image is not None:
            update_data["image"] = submodel.image

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

        if certification is not None:
            new_cert_urls = []
            for cert_item in certification:
                if hasattr(cert_item, "file") and cert_item.filename:
                    os.makedirs(base_dir, exist_ok=True)
                    ext = os.path.splitext(cert_item.filename)[1] or ".pdf"
                    cert_name = f"cert_{len(new_cert_urls)}{ext}"
                    cert_path = os.path.join(base_dir, cert_name)
                    with open(cert_path, "wb") as buf:
                        shutil.copyfileobj(cert_item.file, buf)
                    new_cert_urls.append(f"/qrcodes/Submodels/{submodel_id}/{cert_name}")
                elif isinstance(cert_item, str) and cert_item.strip():
                    new_cert_urls.append(cert_item.strip())
            update_data["certification"] = new_cert_urls

        if update_data:
            product_submodels_collection.update_one({"submodel_id": submodel_id}, {"$set": update_data})

        updated_submodel = product_submodels_collection.find_one({"submodel_id": submodel_id})

        if parsed_variants is not None:
            # Check SKU uniqueness across other submodels
            for item in parsed_variants:
                sku_no = item[2]
                existing_var = product_variants_collection.find_one({"sku_no": sku_no})
                if existing_var and existing_var["submodel_id"] != submodel_id:
                    raise HTTPException(status_code=400, detail=f"Product variant with SKU '{sku_no}' already exists in another submodel")
            
            # Delete any existing variants of this submodel that are not in the new variants list
            new_skus = {item[2] for item in parsed_variants}
            product_variants_collection.delete_many({
                "submodel_id": submodel_id,
                "sku_no": {"$nin": list(new_skus)}
            })

            # Upsert variants
            for item in parsed_variants:
                size_name = item[0]
                size = item[1]
                sku_no = item[2]
                variant_color = item[3] if len(item) > 3 and item[3] is not None else None
                variant_images = item[4] if len(item) > 4 and item[4] is not None else updated_submodel.get("product_images", [])
                
                existing_var = product_variants_collection.find_one({"sku_no": sku_no, "submodel_id": submodel_id})
                if existing_var:
                    product_variants_collection.update_one(
                        {"variant_id": existing_var["variant_id"]},
                        {"$set": {
                            "size_name": size_name,
                            "size": size,
                            "gs1_barcode": updated_submodel.get("gs1_barcode"),
                            "short_description": updated_submodel.get("short_description"),
                            "long_description": updated_submodel.get("long_description"),
                            "carton_box_size": updated_submodel.get("carton_box_size"),
                            "carton_barcode": updated_submodel.get("carton_barcode"),
                            "product_images": variant_images,
                            "color": variant_color,
                            "finish": updated_submodel.get("finish"),
                            "certification": updated_submodel.get("certification", []),
                            "visor_type": updated_submodel.get("visor_type"),
                            "spoiler": updated_submodel.get("spoiler"),
                            "chinstrap_lock": updated_submodel.get("chinstrap_lock"),
                            "pinlock": updated_submodel.get("pinlock"),
                            "mrp": updated_submodel.get("mrp")
                        }}
                    )
                else:
                    variant_id = utils.generate_custom_id("PVAR", product_variants_collection, "variant_id")
                    new_var = {
                        "variant_id": variant_id,
                        "submodel_id": submodel_id,
                        "sku_no": sku_no,
                        "size_name": size_name,
                        "size": size,
                        "is_active": True,
                        "gs1_barcode": updated_submodel.get("gs1_barcode"),
                        "short_description": updated_submodel.get("short_description"),
                        "long_description": updated_submodel.get("long_description"),
                        "carton_box_size": updated_submodel.get("carton_box_size"),
                        "carton_barcode": updated_submodel.get("carton_barcode"),
                        "product_images": variant_images,
                        "color": variant_color,
                        "finish": updated_submodel.get("finish"),
                        "certification": updated_submodel.get("certification", []),
                        "visor_type": updated_submodel.get("visor_type"),
                        "spoiler": updated_submodel.get("spoiler"),
                        "chinstrap_lock": updated_submodel.get("chinstrap_lock"),
                        "pinlock": updated_submodel.get("pinlock"),
                        "mrp": updated_submodel.get("mrp"),
                        "created_by": current_user["user_id"] if current_user else "SYSTEM",
                        "created_at": utils.get_current_time()
                    }
                    product_variants_collection.insert_one(new_var)
        else:
            # Propagate updated submodel fields to ALL existing variants of this submodel
            product_variants_collection.update_many(
                {"submodel_id": submodel_id},
                {"$set": {
                    "gs1_barcode": updated_submodel.get("gs1_barcode"),
                    "short_description": updated_submodel.get("short_description"),
                    "long_description": updated_submodel.get("long_description"),
                    "carton_box_size": updated_submodel.get("carton_box_size"),
                    "carton_barcode": updated_submodel.get("carton_barcode"),
                    "product_images": updated_submodel.get("product_images", []),
                    "finish": updated_submodel.get("finish"),
                    "certification": updated_submodel.get("certification", []),
                    "visor_type": updated_submodel.get("visor_type"),
                    "spoiler": updated_submodel.get("spoiler"),
                    "chinstrap_lock": updated_submodel.get("chinstrap_lock"),
                    "pinlock": updated_submodel.get("pinlock"),
                    "mrp": updated_submodel.get("mrp")
                }}
            )

        updated_submodel.pop("_id", None)
        
        # Resolve Model Info
        model = product_models_collection.find_one({"model_id": updated_submodel["model_id"]})
        updated_submodel["model_name"] = model.get("name") if model else None
        updated_submodel["model_status"] = model.get("is_active") if model else None
        updated_submodel["model_is_active"] = model.get("is_active") if model else None
        brand = product_brands_collection.find_one({"brand_id": model.get("brand_id")}) if model else None
        updated_submodel["brand_id"] = brand.get("brand_id") if brand else None
        updated_submodel["brand_name"] = brand.get("name") if brand else None
        updated_submodel["brand_image"] = brand.get("logo_url") if brand else None
        
        # Fetch current variants
        variants_list = list(product_variants_collection.find(
            {"submodel_id": submodel_id},
            {"_id": 0, "variant_id": 1, "sku_no": 1, "size": 1, "size_name": 1, "color": 1, "product_images": 1}
        )) if submodel_id else []
        updated_submodel["variants"] = variants_list
        return updated_submodel

class ProductVariantOperations:
    @staticmethod
    def create_variant(variant: schemas.ProductVariantCreate, images: List[Union[UploadFile, str]], certification: List[Union[UploadFile, str]], current_user: dict):
        if product_variants_collection.find_one({"sku_no": variant.sku_no}):
            raise HTTPException(status_code=400, detail="Product variant with this SKU number already exists")

        submodel = product_submodels_collection.find_one({"submodel_id": variant.submodel_id})
        if not submodel:
            raise HTTPException(status_code=404, detail="Product submodel not found")

        variant_dict = variant.model_dump()
        variant_id = utils.generate_custom_id("PVAR", product_variants_collection, "variant_id")
        variant_dict["variant_id"] = variant_id
        
        # Robustly handle images which might be empty strings, string urls, or UploadFiles
        image_urls = []
        base_dir = os.path.join("qrcodes", "Variants", variant_id)
        
        # Keep track of existing images or newly uploaded files
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

        variant_dict["created_by"] = current_user["user_id"]
        variant_dict["created_at"] = utils.get_current_time()

        # Insert raw variant data only to keep DB clean and normalize references
        product_variants_collection.insert_one(variant_dict)
        variant_dict.pop("_id", None)

        # Resolve complete upward hierarchy dynamically for the return payload
        model = product_models_collection.find_one({"model_id": submodel["model_id"]}) if submodel else None
        brand = product_brands_collection.find_one({"brand_id": model["brand_id"]}) if model else None
        category = product_categories_collection.find_one({"category_id": model["category_id"]}) if model else None
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model["subcategory_id"]}) if model else None

        variant_dict["submodel_name"] = submodel.get("name") if submodel else None
        variant_dict["submodel_image"] = submodel.get("image") if submodel else None
        variant_dict["submodel_status"] = submodel.get("is_active") if submodel else None
        variant_dict["submodel_is_active"] = submodel.get("is_active") if submodel else None

        variant_dict["box_weight"] = submodel.get("box_weight") if submodel else None
        variant_dict["box_dimension"] = submodel.get("box_dimension") if submodel else None
        variant_dict["carton_weight"] = submodel.get("carton_weight") if submodel else None
        variant_dict["carton_dimension"] = submodel.get("carton_dimension") if submodel else None

        variant_dict["model_id"] = model.get("model_id") if model else None
        variant_dict["model_name"] = model.get("name") if model else None
        variant_dict["model_status"] = model.get("is_active") if model else None
        variant_dict["model_is_active"] = model.get("is_active") if model else None

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
    def get_variants(submodel_id: Optional[str] = None, page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if submodel_id:
            query["submodel_id"] = submodel_id
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

            v["box_weight"] = submodel.get("box_weight") if submodel else None
            v["box_dimension"] = submodel.get("box_dimension") if submodel else None
            v["carton_weight"] = submodel.get("carton_weight") if submodel else None
            v["carton_dimension"] = submodel.get("carton_dimension") if submodel else None

            v["model_id"] = model.get("model_id") if model else None
            v["model_name"] = model.get("name") if model else None
            v["model_status"] = model.get("is_active") if model else None
            v["model_is_active"] = model.get("is_active") if model else None

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
        image_urls = existing.get("product_images", [])
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

        # Robustly handle certification list (can be overwritten or cleared)
        if certification is not None:
            cert_urls = []
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
            update_data["certification"] = cert_urls
            
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

        updated["box_weight"] = submodel.get("box_weight") if submodel else None
        updated["box_dimension"] = submodel.get("box_dimension") if submodel else None
        updated["carton_weight"] = submodel.get("carton_weight") if submodel else None
        updated["carton_dimension"] = submodel.get("carton_dimension") if submodel else None

        updated["model_id"] = model.get("model_id") if model else None
        updated["model_name"] = model.get("name") if model else None
        updated["model_status"] = model.get("is_active") if model else None
        updated["model_is_active"] = model.get("is_active") if model else None

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

            v["box_weight"] = submodel.get("box_weight") if submodel else None
            v["box_dimension"] = submodel.get("box_dimension") if submodel else None
            v["carton_weight"] = submodel.get("carton_weight") if submodel else None
            v["carton_dimension"] = submodel.get("carton_dimension") if submodel else None

            v["model_id"] = model.get("model_id") if model else None
            v["model_name"] = model.get("name") if model else None
            v["model_status"] = model.get("is_active") if model else None
            v["model_is_active"] = model.get("is_active") if model else None

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

        variant["box_weight"] = submodel.get("box_weight") if submodel else None
        variant["box_dimension"] = submodel.get("box_dimension") if submodel else None
        variant["carton_weight"] = submodel.get("carton_weight") if submodel else None
        variant["carton_dimension"] = submodel.get("carton_dimension") if submodel else None

        variant["model_id"] = model.get("model_id") if model else None
        variant["model_name"] = model.get("name") if model else None
        variant["model_status"] = model.get("is_active") if model else None
        variant["model_is_active"] = model.get("is_active") if model else None

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

@router.get("/categories/", response_model=List[dict])
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
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProductBrandOperations.create_brand(name, description, logo, is_active, current_user)

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
    return ProductBrandOperations.update_brand(brand_id, brand.is_active)

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
    search: str = Query("")
):
    return ProductModelOperations.get_models(page=page, limit=limit, search=search)

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
    image: Optional[UploadFile] = File(None),
    is_active: bool = Form(True),
    box_weight: Optional[float] = Form(None),
    box_dimension: Optional[str] = Form(None),
    carton_weight: Optional[float] = Form(None),
    carton_dimension: Optional[str] = Form(None),
    
    # Variant fields at submodel level
    gs1_barcode: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    long_description: Optional[str] = Form(None),
    carton_box_size: Optional[int] = Form(None),
    carton_barcode: Optional[str] = Form(None),
    finish: Optional[str] = Form(None),
    visor_type: Optional[str] = Form(None),
    spoiler: Optional[str] = Form(None),
    chinstrap_lock: Optional[str] = Form(None),
    pinlock: Optional[str] = Form(None),
    mrp: Optional[str] = Form(None),
    images: list[UploadFile] = File(default=[]),
    certification: Optional[Union[List[str], str]] = Form(None),
    variants: Optional[str] = Form(None),
    
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    valid_images = []
    if isinstance(images, list):
        valid_images = [img for img in images if hasattr(img, "file") and getattr(img, "filename", None)]
    elif hasattr(images, "file") and getattr(images, "filename", None):
        valid_images = [images]

    valid_certs = []
    if certification is not None:
        if isinstance(certification, list):
            for c in certification:
                if isinstance(c, str) and c.strip():
                    if c.strip().startswith("[") and c.strip().endswith("]"):
                        import json
                        try:
                            parsed = json.loads(c.strip())
                            if isinstance(parsed, list):
                                valid_certs.extend([str(item).strip() for item in parsed if str(item).strip()])
                            else:
                                valid_certs.append(str(parsed).strip())
                        except Exception:
                            valid_certs.append(c.strip())
                    else:
                        valid_certs.append(c.strip())
        elif isinstance(certification, str):
            if certification.strip().startswith("[") and certification.strip().endswith("]"):
                import json
                try:
                    parsed = json.loads(certification.strip())
                    if isinstance(parsed, list):
                        valid_certs.extend([str(item).strip() for item in parsed if str(item).strip()])
                    else:
                        valid_certs.append(str(parsed).strip())
                except Exception:
                    valid_certs.append(certification.strip())
            elif "," in certification:
                valid_certs = [c.strip() for c in certification.split(",") if c.strip()]
            elif certification.strip():
                valid_certs.append(certification.strip())

    parsed_mrp = None
    if mrp is not None:
        mrp_str = str(mrp).strip()
        if mrp_str.startswith("{") and mrp_str.endswith("}"):
            import json
            try:
                parsed_mrp = json.loads(mrp_str)
                if isinstance(parsed_mrp, dict):
                    parsed_mrp = {k: float(v) for k, v in parsed_mrp.items()}
            except Exception:
                try:
                    parsed_mrp = {"INR": float(mrp_str)}
                except Exception:
                    parsed_mrp = None
        else:
            try:
                parsed_mrp = {"INR": float(mrp_str)}
            except Exception:
                parsed_mrp = None

    parsed_variants = []
    if variants:
        import json
        try:
            parsed_variants = json.loads(variants)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid format for variants. Must be a JSON array of arrays like [['s', 80, 'SKU-567']]")
        
        if not isinstance(parsed_variants, list) or not all(isinstance(v, list) and 3 <= len(v) <= 5 for v in parsed_variants):
            raise HTTPException(status_code=400, detail="Variants must be a list of lists of length 3 to 5: [size_name, size, sku_no, color (optional), product_images (optional)]")

    submodel_schema = schemas.ProductSubModelCreate(
        name=name,
        model_id=model_id,
        image=None,
        is_active=is_active,
        box_weight=box_weight,
        box_dimension=box_dimension,
        carton_weight=carton_weight,
        carton_dimension=carton_dimension,
        gs1_barcode=gs1_barcode,
        short_description=short_description,
        long_description=long_description,
        carton_box_size=carton_box_size,
        carton_barcode=carton_barcode,
        product_images=[],
        finish=finish,
        certification=[],
        visor_type=visor_type,
        spoiler=spoiler,
        chinstrap_lock=chinstrap_lock,
        pinlock=pinlock,
        mrp=parsed_mrp
    )
    return ProductSubModelOperations.create_submodel(
        submodel_schema, image, valid_images, valid_certs, parsed_variants, current_user
    )

@router.get("/submodels/", response_model=dict)
def get_product_submodels(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query("")
):
    return ProductSubModelOperations.get_submodels(page=page, limit=limit, search=search)

@router.put("/submodels/{submodel_id}", response_model=dict)
def update_product_submodel(
    submodel_id: str,
    name: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    is_active: Optional[bool] = Form(None),
    box_weight: Optional[float] = Form(None),
    box_dimension: Optional[str] = Form(None),
    carton_weight: Optional[float] = Form(None),
    carton_dimension: Optional[str] = Form(None),
    
    # New variant fields at submodel level
    gs1_barcode: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    long_description: Optional[str] = Form(None),
    carton_box_size: Optional[int] = Form(None),
    carton_barcode: Optional[str] = Form(None),
    finish: Optional[str] = Form(None),
    visor_type: Optional[str] = Form(None),
    spoiler: Optional[str] = Form(None),
    chinstrap_lock: Optional[str] = Form(None),
    pinlock: Optional[str] = Form(None),
    mrp: Optional[str] = Form(None),
    images: Optional[list[UploadFile]] = File(default=None),
    certification: Optional[Union[List[str], str]] = Form(None),
    variants: Optional[str] = Form(None),
    
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    valid_images = None
    if images is not None:
        valid_images = []
        if isinstance(images, list):
            valid_images = [img for img in images if hasattr(img, "file") and getattr(img, "filename", None)]
        elif hasattr(images, "file") and getattr(images, "filename", None):
            valid_images = [images]

    valid_certs = None
    if certification is not None:
        valid_certs = []
        if isinstance(certification, list):
            for c in certification:
                if isinstance(c, str) and c.strip():
                    if c.strip().startswith("[") and c.strip().endswith("]"):
                        import json
                        try:
                            parsed = json.loads(c.strip())
                            if isinstance(parsed, list):
                                valid_certs.extend([str(item).strip() for item in parsed if str(item).strip()])
                            else:
                                valid_certs.append(str(parsed).strip())
                        except Exception:
                            valid_certs.append(c.strip())
                    else:
                        valid_certs.append(c.strip())
        elif isinstance(certification, str):
            if certification.strip().startswith("[") and certification.strip().endswith("]"):
                import json
                try:
                    parsed = json.loads(certification.strip())
                    if isinstance(parsed, list):
                        valid_certs.extend([str(item).strip() for item in parsed if str(item).strip()])
                    else:
                        valid_certs.append(str(parsed).strip())
                except Exception:
                    valid_certs.append(certification.strip())
            elif "," in certification:
                valid_certs = [c.strip() for c in certification.split(",") if c.strip()]
            elif certification.strip():
                valid_certs.append(certification.strip())

    parsed_mrp = None
    if mrp is not None:
        mrp_str = str(mrp).strip()
        if mrp_str.startswith("{") and mrp_str.endswith("}"):
            import json
            try:
                parsed_mrp = json.loads(mrp_str)
                if isinstance(parsed_mrp, dict):
                    parsed_mrp = {k: float(v) for k, v in parsed_mrp.items()}
            except Exception:
                try:
                    parsed_mrp = {"INR": float(mrp_str)}
                except Exception:
                    parsed_mrp = None
        else:
            try:
                parsed_mrp = {"INR": float(mrp_str)}
            except Exception:
                parsed_mrp = None

    parsed_variants = None
    if variants is not None:
        import json
        try:
            parsed_variants = json.loads(variants)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid format for variants. Must be a JSON array of arrays like [['s', 80, 'SKU-567']]")
        
        if not isinstance(parsed_variants, list) or not all(isinstance(v, list) and 3 <= len(v) <= 5 for v in parsed_variants):
            raise HTTPException(status_code=400, detail="Variants must be a list of lists of length 3 to 5: [size_name, size, sku_no, color (optional), product_images (optional)]")

    submodel_schema = schemas.ProductSubModelUpdate(
        image=None,
        is_active=is_active,
        box_weight=box_weight,
        box_dimension=box_dimension,
        carton_weight=carton_weight,
        carton_dimension=carton_dimension,
        
        # New variant fields stored on submodel
        gs1_barcode=gs1_barcode,
        short_description=short_description,
        long_description=long_description,
        carton_box_size=carton_box_size,
        carton_barcode=carton_barcode,
        product_images=None,
        finish=finish,
        certification=None,
        visor_type=visor_type,
        spoiler=spoiler,
        chinstrap_lock=chinstrap_lock,
        pinlock=pinlock,
        mrp=parsed_mrp
    )
    return ProductSubModelOperations.update_submodel(
        submodel_id=submodel_id,
        submodel=submodel_schema,
        name=name,
        image_file=image,
        images=valid_images,
        certification=valid_certs,
        parsed_variants=parsed_variants,
        current_user=current_user
    )



@router.get("/variants/", response_model=dict)
def get_product_variants(
    submodel_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query("")
):
    return ProductVariantOperations.get_variants(submodel_id, page=page, limit=limit, search=search)

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


