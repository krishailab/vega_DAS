import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from .. import schemas, auth, utils
from ..database import (
    b2b_inward_products_collection,
    product_variants_collection,
    product_submodels_collection,
    product_models_collection,
    product_brands_collection,
    product_categories_collection,
    product_subcategories_collection,
    b2b_coupons_collection,
    users_collection,
    b2b_config_collection,
    b2b_orders_collection,
    b2b_gst_settings_collection
)


router = APIRouter(prefix="/api/v1/b2b-admin", tags=["B2B Admin"])

class B2BInwardOperations:
    @staticmethod
    def create_inward(inward_data: schemas.B2BInwardProductCreate, current_user: dict) -> dict:
        # 1. Verify master product variant exists
        variant = product_variants_collection.find_one({"variant_id": inward_data.variant_id})
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Master product variant with ID '{inward_data.variant_id}' does not exist"
            )

        # 2. Check for duplicate B2B inward
        existing = b2b_inward_products_collection.find_one({"variant_id": inward_data.variant_id})
        if existing:
            existing_qty = existing.get("quantity")
            added_qty = inward_data.quantity
            
            if existing_qty is not None or added_qty is not None:
                new_qty = (existing_qty or 0) + (added_qty or 0)
            else:
                new_qty = None
                
            b2b_inward_products_collection.update_one(
                {"variant_id": inward_data.variant_id},
                {
                    "$set": {
                        "quantity": new_qty,
                        "updated_at": utils.get_current_time()
                    }
                }
            )
            updated = b2b_inward_products_collection.find_one({"variant_id": inward_data.variant_id})
            updated.pop("_id", None)
            return updated

        # 3. Generate inward_id & build document
        inward_id = utils.generate_custom_id("B2B-INW", b2b_inward_products_collection, "inward_id")
        
        inward_dict = inward_data.model_dump() if hasattr(inward_data, "model_dump") else inward_data.dict()
        inward_dict["inward_id"] = inward_id
        inward_dict["sku_no"] = variant.get("sku_no")
        inward_dict["created_by"] = current_user["user_id"]
        inward_dict["created_at"] = utils.get_current_time()
        inward_dict["updated_at"] = utils.get_current_time()

        # 4. Insert into database
        b2b_inward_products_collection.insert_one(inward_dict)
        inward_dict.pop("_id", None)
        return inward_dict

    @staticmethod
    def get_inwards(
        is_featured: Optional[bool] = None,
        is_new_arrival: Optional[bool] = None,
        is_best_seller: Optional[bool] = None,
        is_active: Optional[bool] = None,
        is_individual: Optional[bool] = None,
        is_carton: Optional[bool] = None
    ) -> List[dict]:
        query = {}
        if is_featured is not None:
            query["is_featured"] = is_featured
        if is_new_arrival is not None:
            query["is_new_arrival"] = is_new_arrival
        if is_best_seller is not None:
            query["is_best_seller"] = is_best_seller
        if is_active is not None:
            query["is_active"] = is_active
        if is_individual is not None:
            query["is_individual"] = is_individual
        if is_carton is not None:
            query["is_carton"] = is_carton

        inwards = list(b2b_inward_products_collection.find(query))

        # Prefetch referenced collections to avoid N+1 query overhead
        categories_by_id = {c["category_id"]: c for c in product_categories_collection.find()}
        subcategories_by_id = {s["subcategory_id"]: s for s in product_subcategories_collection.find()}
        brands_by_id = {b["brand_id"]: b for b in product_brands_collection.find()}
        models_by_id = {m["model_id"]: m for m in product_models_collection.find()}
        submodels_by_id = {sm["submodel_id"]: sm for sm in product_submodels_collection.find()}
        variants_by_id = {v["variant_id"]: v for v in product_variants_collection.find()}

        results = []
        for inw in inwards:
            inw.pop("_id", None)
            variant_id = inw["variant_id"]
            variant = variants_by_id.get(variant_id)
            
            resolved_variant = {}
            if variant:
                resolved_variant = dict(variant)
                resolved_variant.pop("_id", None)
                
                # Resolve upward hierarchy
                submodel = submodels_by_id.get(variant["submodel_id"])
                model = models_by_id.get(submodel["model_id"]) if submodel else None
                brand = brands_by_id.get(model["brand_id"]) if model else None
                category = categories_by_id.get(model["category_id"]) if model else None
                subcategory = subcategories_by_id.get(model["subcategory_id"]) if model else None

                resolved_variant["submodel_name"] = submodel.get("name") if submodel else None
                resolved_variant["submodel_image"] = submodel.get("image") if submodel else None
                resolved_variant["submodel_status"] = submodel.get("is_active") if submodel else None
                resolved_variant["submodel_is_active"] = submodel.get("is_active") if submodel else None

                resolved_variant["model_id"] = model.get("model_id") if model else None
                resolved_variant["model_name"] = model.get("name") if model else None
                resolved_variant["model_status"] = model.get("is_active") if model else None
                resolved_variant["model_is_active"] = model.get("is_active") if model else None

                resolved_variant["brand_id"] = brand.get("brand_id") if brand else None
                resolved_variant["brand_name"] = brand.get("name") if brand else None
                resolved_variant["brand_status"] = brand.get("is_active") if brand else None
                resolved_variant["brand_is_active"] = brand.get("is_active") if brand else None

                resolved_variant["category_id"] = category.get("category_id") if category else None
                resolved_variant["category_name"] = category.get("name") if category else None
                resolved_variant["category_status"] = category.get("is_active") if category else None
                resolved_variant["category_is_active"] = category.get("is_active") if category else None

                resolved_variant["subcategory_id"] = subcategory.get("subcategory_id") if subcategory else None
                resolved_variant["subcategory_name"] = subcategory.get("name") if subcategory else None
                resolved_variant["subcategory_status"] = subcategory.get("is_active") if subcategory else None
                resolved_variant["subcategory_is_active"] = subcategory.get("is_active") if subcategory else None

            results.append({
                "inward_detail": inw,
                "variant_detail": resolved_variant
            })

        return results

    @staticmethod
    def get_inward_cards(
        is_featured: Optional[bool] = None,
        is_new_arrival: Optional[bool] = None,
        is_best_seller: Optional[bool] = None,
        is_active: Optional[bool] = None,
        is_individual: Optional[bool] = None,
        is_carton: Optional[bool] = None,
        category_id: Optional[str] = None,
        subcategory_id: Optional[str] = None,
        brand_id: Optional[str] = None,
        model_id: Optional[str] = None,
        submodel_id: Optional[str] = None,
        color: Optional[str] = None,
        size: Optional[int] = None,
        size_name: Optional[str] = None,
        chinstrap_lock: Optional[str] = None,
    ) -> List[dict]:
        query = {}
        if is_featured is not None:
            query["is_featured"] = is_featured
        if is_new_arrival is not None:
            query["is_new_arrival"] = is_new_arrival
        if is_best_seller is not None:
            query["is_best_seller"] = is_best_seller
        if is_active is not None:
            query["is_active"] = is_active
        if is_individual is not None:
            query["is_individual"] = is_individual
        if is_carton is not None:
            query["is_carton"] = is_carton

        inwards = list(b2b_inward_products_collection.find(query))

        # Prefetch only referenced documents to optimize performance and memory usage
        variant_ids = list(set(inw["variant_id"] for inw in inwards if inw.get("variant_id")))
        variants_by_id = {v["variant_id"]: v for v in product_variants_collection.find({"variant_id": {"$in": variant_ids}})}

        submodel_ids = list(set(v["submodel_id"] for v in variants_by_id.values() if v.get("submodel_id")))
        submodels_by_id = {sm["submodel_id"]: sm for sm in product_submodels_collection.find({"submodel_id": {"$in": submodel_ids}})}

        model_ids = list(set(sm["model_id"] for sm in submodels_by_id.values() if sm.get("model_id")))
        models_by_id = {m["model_id"]: m for m in product_models_collection.find({"model_id": {"$in": model_ids}})}

        brand_ids = list(set(m["brand_id"] for m in models_by_id.values() if m.get("brand_id")))
        brands_by_id = {b["brand_id"]: b for b in product_brands_collection.find({"brand_id": {"$in": brand_ids}})}

        category_ids = list(set(m["category_id"] for m in models_by_id.values() if m.get("category_id")))
        categories_by_id = {c["category_id"]: c for c in product_categories_collection.find({"category_id": {"$in": category_ids}})}

        subcategory_ids = list(set(m["subcategory_id"] for m in models_by_id.values() if m.get("subcategory_id")))
        subcategories_by_id = {s["subcategory_id"]: s for s in product_subcategories_collection.find({"subcategory_id": {"$in": subcategory_ids}})}

        submodels_map = {}
        for inw in inwards:
            variant_id = inw["variant_id"]
            variant = variants_by_id.get(variant_id)
            if not variant:
                continue

            submodel_id_val = variant.get("submodel_id")
            submodel = submodels_by_id.get(submodel_id_val)
            if not submodel:
                continue

            model = models_by_id.get(submodel["model_id"])

            # ── Hierarchy filters ──────────────────────────────────────
            if category_id and (not model or model.get("category_id") != category_id):
                continue
            if subcategory_id and (not model or model.get("subcategory_id") != subcategory_id):
                continue
            if brand_id and (not model or model.get("brand_id") != brand_id):
                continue
            if model_id and (not model or model.get("model_id") != model_id):
                continue
            if submodel_id and submodel_id_val != submodel_id:
                continue

            # ── Variant-level filters ──────────────────────────────────
            # A submodel card is included only if at least one variant matches.
            if color and variant.get("color", "").strip().lower() != color.strip().lower():
                continue
            if size is not None and variant.get("size") != size:
                continue
            if size_name and variant.get("size_name", "").strip().lower() != size_name.strip().lower():
                continue
            if chinstrap_lock and variant.get("chinstrap_lock", "").strip().upper() != chinstrap_lock.strip().upper():
                continue

            brand = brands_by_id.get(model["brand_id"]) if model else None
            category = categories_by_id.get(model["category_id"]) if model else None
            subcategory = subcategories_by_id.get(model["subcategory_id"]) if model else None

            brand_name = brand.get("name") if brand else ""
            model_name = model.get("name") if model else ""
            submodel_name = submodel.get("name") if submodel else ""
            
            # Construct beautiful resolved name for the submodel
            name_parts = [part for part in [brand_name, model_name, submodel_name] if part]
            resolved_name = " ".join(name_parts) if name_parts else (submodel_name or "Unknown")

            image_url = submodel.get("image")

            inw_currency = inw.get("currency", "INR")
            dealer_price = float(inw.get("dealer_price", 0))

            card_variant = {
                "variant_id": variant_id,
                "sku_no": variant.get("sku_no", ""),
                "color": variant.get("color") or submodel.get("color"),
                "size": variant.get("size"),
                "size_name": variant.get("size_name"),
                "dealer_price": dealer_price,
                "currency": inw_currency,
                "quantity": inw.get("quantity"),
                "inward_id": inw["inward_id"],
                "is_active": inw.get("is_active", False)
            }

            if submodel_id_val not in submodels_map:
                submodels_map[submodel_id_val] = {
                    "submodel_id": submodel_id_val,
                    "name": resolved_name,
                    "image": image_url,
                    "color": submodel.get("color"),
                    "finish": submodel.get("finish"),
                    "product_images": submodel.get("product_images", []),
                    "starting_price": dealer_price,
                    "currency": inw_currency,
                    "total_variants": 1,
                    "is_active": inw.get("is_active", False),
                    "is_featured": inw.get("is_featured", False),
                    "is_new_arrival": inw.get("is_new_arrival", False),
                    "is_best_seller": inw.get("is_best_seller", False),
                    "category_id": category.get("category_id") if category else None,
                    "category_name": category.get("name") if category else None,
                    "subcategory_id": subcategory.get("subcategory_id") if subcategory else None,
                    "subcategory_name": subcategory.get("name") if subcategory else None,
                    "brand_id": brand.get("brand_id") if brand else None,
                    "brand_name": brand_name,
                    "model_id": model.get("model_id") if model else None,
                    "model_name": model_name,
                    "variants": [card_variant]
                }
            else:
                card = submodels_map[submodel_id_val]
                card["total_variants"] += 1
                if dealer_price < card["starting_price"]:
                    card["starting_price"] = dealer_price
                # Aggregate boolean flags
                card["is_active"] = card["is_active"] or inw.get("is_active", False)
                card["is_featured"] = card["is_featured"] or inw.get("is_featured", False)
                card["is_new_arrival"] = card["is_new_arrival"] or inw.get("is_new_arrival", False)
                card["is_best_seller"] = card["is_best_seller"] or inw.get("is_best_seller", False)
                card["variants"].append(card_variant)

        return list(submodels_map.values())

    @staticmethod
    def get_inward_detail(inward_id: str) -> dict:
        # Treat inward_id conceptually as submodel_id for the detail view
        submodel_id = inward_id
        submodel = product_submodels_collection.find_one({"submodel_id": submodel_id})
        if not submodel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submodel with ID '{submodel_id}' not found"
            )
            
        model = product_models_collection.find_one({"model_id": submodel["model_id"]})
        brand = product_brands_collection.find_one({"brand_id": model["brand_id"]}) if model else None
        category = product_categories_collection.find_one({"category_id": model["category_id"]}) if model else None
        subcategory = product_subcategories_collection.find_one({"subcategory_id": model["subcategory_id"]}) if model else None
        
        submodel_detail = {
            "submodel_id": submodel["submodel_id"],
            "name": submodel.get("name"),
            "image": submodel.get("image"),
            "is_active": submodel.get("is_active"),
            "model_id": model.get("model_id") if model else None,
            "model_name": model.get("name") if model else None,
            "brand_id": brand.get("brand_id") if brand else None,
            "brand_name": brand.get("name") if brand else None,
            "category_id": category.get("category_id") if category else None,
            "category_name": category.get("name") if category else None,
            "subcategory_id": subcategory.get("subcategory_id") if subcategory else None,
            "subcategory_name": subcategory.get("name") if subcategory else None,
            
            # Submodel level fields
            "color": submodel.get("color"),
            "finish": submodel.get("finish"),
            "mrp": submodel.get("mrp"),
            "certification": submodel.get("certification", []),
            "visor_type": submodel.get("visor_type"),
            "spoiler": submodel.get("spoiler"),
            "chinstrap_lock": submodel.get("chinstrap_lock"),
            "pinlock": submodel.get("pinlock"),
            "carton_box_size": submodel.get("carton_box_size"),
            "carton_barcode": submodel.get("carton_barcode"),
            "product_images": submodel.get("product_images", []),
            "gs1_barcode": submodel.get("gs1_barcode"),
            "short_description": submodel.get("short_description"),
            "long_description": submodel.get("long_description")
        }
        
        variants = []
        variants_cursor = product_variants_collection.find({"submodel_id": submodel_id})
        
        for v in variants_cursor:
            v_id = v["variant_id"]
            b2b_inw = b2b_inward_products_collection.find_one({"variant_id": v_id})
            
            # Skip if the variant is not inwarded in B2B catalog
            if not b2b_inw:
                continue
                
            b2b_inw.pop("_id", None)
            
            variants.append({
                "variant_id": v_id,
                "sku_no": v.get("sku_no"),
                "size": v.get("size"),
                "size_name": v.get("size_name"),
                "color": v.get("color") or submodel.get("color"),
                "finish": v.get("finish") or submodel.get("finish"),
                "is_active": v.get("is_active"),
                "mrp": v.get("mrp") or submodel.get("mrp"),
                "product_images": v.get("product_images") or submodel.get("product_images", []),
                "b2b_inward": b2b_inw
            })
            
        return {
            "submodel_detail": submodel_detail,
            "variants": variants
        }

    @staticmethod
    def update_inward(inward_id: str, update_data: schemas.B2BInwardProductUpdate) -> dict:
        inward = b2b_inward_products_collection.find_one({"inward_id": inward_id})
        if not inward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"B2B inwarded product with ID '{inward_id}' not found"
            )

        update_dict = update_data.model_dump(exclude_unset=True) if hasattr(update_data, "model_dump") else update_data.dict(exclude_unset=True)
        
        if update_dict:
            update_dict["updated_at"] = utils.get_current_time()
            b2b_inward_products_collection.update_one({"inward_id": inward_id}, {"$set": update_dict})

        updated = b2b_inward_products_collection.find_one({"inward_id": inward_id})
        updated.pop("_id", None)
        return updated

    @staticmethod
    def delete_inward(inward_id: str) -> dict:
        inward = b2b_inward_products_collection.find_one({"inward_id": inward_id})
        if not inward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"B2B inwarded product with ID '{inward_id}' not found"
            )

        b2b_inward_products_collection.delete_one({"inward_id": inward_id})
        return {"status": "success", "message": f"Inwarded product '{inward_id}' deleted successfully"}

    @staticmethod
    def get_filter_options() -> dict:
        variant_ids = b2b_inward_products_collection.distinct("variant_id")
        
        # Only prefetch variants that have active inwards
        variants = list(product_variants_collection.find(
            {"variant_id": {"$in": variant_ids}},
            {"variant_id": 1, "submodel_id": 1, "color": 1, "size": 1, "size_name": 1, "_id": 0}
        ))
        
        submodel_ids = list({v["submodel_id"] for v in variants if v.get("submodel_id")})
        submodels_cursor = product_submodels_collection.find(
            {"submodel_id": {"$in": submodel_ids}},
            {"submodel_id": 1, "model_id": 1, "_id": 0}
        ) if submodel_ids else []
        submodels_by_id = {sm["submodel_id"]: sm for sm in submodels_cursor}
        
        model_ids = list({sm["model_id"] for sm in submodels_by_id.values() if sm.get("model_id")})
        models_cursor = product_models_collection.find(
            {"model_id": {"$in": model_ids}},
            {"model_id": 1, "brand_id": 1, "category_id": 1, "subcategory_id": 1, "_id": 0}
        ) if model_ids else []
        models_by_id = {m["model_id"]: m for m in models_cursor}
        
        brand_ids = list({m["brand_id"] for m in models_by_id.values() if m.get("brand_id")})
        brands_cursor = product_brands_collection.find(
            {"brand_id": {"$in": brand_ids}},
            {"brand_id": 1, "name": 1, "_id": 0}
        ) if brand_ids else []
        brands_by_id = {b["brand_id"]: b for b in brands_cursor}
        
        category_ids = list({m["category_id"] for m in models_by_id.values() if m.get("category_id")})
        categories_cursor = product_categories_collection.find(
            {"category_id": {"$in": category_ids}},
            {"category_id": 1, "name": 1, "_id": 0}
        ) if category_ids else []
        categories_by_id = {c["category_id"]: c for c in categories_cursor}
        
        subcategory_ids = list({m["subcategory_id"] for m in models_by_id.values() if m.get("subcategory_id")})
        subcategories_cursor = product_subcategories_collection.find(
            {"subcategory_id": {"$in": subcategory_ids}},
            {"subcategory_id": 1, "name": 1, "category_id": 1, "_id": 0}
        ) if subcategory_ids else []
        subcategories_by_id = {s["subcategory_id"]: s for s in subcategories_cursor}

        used_categories = {}
        used_subcategories = {}
        used_brands = {}
        used_colors = set()
        used_sizes = set()
        used_size_names = set()

        for variant in variants:
            submodel = submodels_by_id.get(variant.get("submodel_id"))
            model = models_by_id.get(submodel.get("model_id")) if submodel else None

            if model:
                brand = brands_by_id.get(model.get("brand_id"))
                if brand:
                    used_brands[brand["brand_id"]] = {
                        "brand_id": brand["brand_id"],
                        "name": brand["name"]
                    }

                category = categories_by_id.get(model.get("category_id"))
                if category:
                    used_categories[category["category_id"]] = {
                        "category_id": category["category_id"],
                        "name": category["name"]
                    }

                subcategory = subcategories_by_id.get(model.get("subcategory_id"))
                if subcategory:
                    used_subcategories[subcategory["subcategory_id"]] = {
                        "subcategory_id": subcategory["subcategory_id"],
                        "name": subcategory["name"],
                        "category_id": subcategory["category_id"]
                    }

            color = variant.get("color")
            if color:
                used_colors.add(color)

            size = variant.get("size")
            if size is not None:
                used_sizes.add(size)

            size_name = variant.get("size_name")
            if size_name:
                used_size_names.add(size_name)

        return {
            "categories": sorted(list(used_categories.values()), key=lambda x: x["name"]),
            "subcategories": sorted(list(used_subcategories.values()), key=lambda x: x["name"]),
            "brands": sorted(list(used_brands.values()), key=lambda x: x["name"]),
            "colors": sorted(list(used_colors)),
            "sizes": sorted(list(used_sizes)),
            "size_names": sorted(list(used_size_names))
        }


class B2BCouponOperations:
    @staticmethod
    def create_coupon(coupon_data: schemas.B2BCouponCreate, current_user: dict) -> dict:
        existing = b2b_coupons_collection.find_one({"coupon_code": coupon_data.coupon_code})
        if existing:
            raise HTTPException(status_code=400, detail="Coupon code already exists")
        
        coupon_id = utils.generate_custom_id("CUPN", b2b_coupons_collection, "coupon_id")
        coupon_dict = coupon_data.model_dump() if hasattr(coupon_data, "model_dump") else coupon_data.dict()
        coupon_dict["coupon_id"] = coupon_id
        coupon_dict["created_by"] = current_user["user_id"]
        coupon_dict["created_at"] = utils.get_current_time()
        coupon_dict["updated_at"] = utils.get_current_time()
        
        b2b_coupons_collection.insert_one(coupon_dict)
        coupon_dict.pop("_id", None)
        return coupon_dict

    @staticmethod
    def get_coupons(page: int = 1, limit: int = 50, search: str = "") -> List[dict]:
        query = {}
        if search:
            query["$or"] = [
                {"code": {"$regex": search, "$options": "i"}},
                {"coupon_id": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        skip = (page - 1) * limit
        coupons = list(b2b_coupons_collection.find(query).skip(skip).limit(limit))
        for c in coupons:
            c.pop("_id", None)
        return coupons

    @staticmethod
    def get_coupon(coupon_id: str) -> dict:
        coupon = b2b_coupons_collection.find_one({"coupon_id": coupon_id})
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
        coupon.pop("_id", None)
        return coupon

    @staticmethod
    def update_coupon(coupon_id: str, update_data: schemas.B2BCouponUpdate) -> dict:
        coupon = b2b_coupons_collection.find_one({"coupon_id": coupon_id})
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
            
        update_dict = update_data.model_dump(exclude_unset=True) if hasattr(update_data, "model_dump") else update_data.dict(exclude_unset=True)
        if update_dict:
            update_dict["updated_at"] = utils.get_current_time()
            b2b_coupons_collection.update_one({"coupon_id": coupon_id}, {"$set": update_dict})
            
        updated = b2b_coupons_collection.find_one({"coupon_id": coupon_id})
        updated.pop("_id", None)
        return updated

    @staticmethod
    def delete_coupon(coupon_id: str) -> dict:
        coupon = b2b_coupons_collection.find_one({"coupon_id": coupon_id})
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
        b2b_coupons_collection.delete_one({"coupon_id": coupon_id})
        return {"status": "success", "message": "Coupon deleted successfully"}


class B2BLimitsOperations:
    @staticmethod
    def get_default_limits() -> dict:
        cfg = b2b_config_collection.find_one({"config_id": "limits"})
        if not cfg:
            cfg = {
                "config_id": "limits",
                "order_credit_limit": None,
                "overall_credit_limit": None,
                "updated_at": utils.get_current_time(),
                "updated_by": "system"
            }
            b2b_config_collection.insert_one(cfg)
        cfg.pop("_id", None)
        return cfg

    @staticmethod
    def update_default_limits(data: schemas.B2BLimitsUpdate, current_user: dict) -> dict:
        update_fields = {}
        if data.order_credit_limit is not None:
            update_fields["order_credit_limit"] = data.order_credit_limit
        if data.overall_credit_limit is not None:
            update_fields["overall_credit_limit"] = data.overall_credit_limit

        update_fields["updated_at"] = utils.get_current_time()
        update_fields["updated_by"] = current_user["user_id"]

        b2b_config_collection.update_one(
            {"config_id": "limits"},
            {"$set": update_fields},
            upsert=True
        )
        return B2BLimitsOperations.get_default_limits()

    @staticmethod
    def update_dealer_limits(dealer_id: str, data: schemas.B2BLimitsUpdate) -> dict:
        dealer = users_collection.find_one({"user_id": dealer_id, "role": "Dealer"})
        if not dealer:
            raise HTTPException(status_code=404, detail="Dealer not found")

        update_fields = {}
        if data.order_credit_limit is not None:
            update_fields["order_credit_limit"] = data.order_credit_limit
        if data.overall_credit_limit is not None:
            update_fields["overall_credit_limit"] = data.overall_credit_limit

        if update_fields:
            users_collection.update_one(
                {"user_id": dealer_id},
                {"$set": update_fields}
            )

        updated_dealer = users_collection.find_one({"user_id": dealer_id})
        updated_dealer.pop("_id", None)
        updated_dealer.pop("password", None)
        return updated_dealer

    @staticmethod
    def renew_dealer_credit(dealer_id: str) -> dict:
        dealer = users_collection.find_one({"user_id": dealer_id, "role": "Dealer"})
        if not dealer:
            raise HTTPException(status_code=404, detail="Dealer not found")

        result = b2b_orders_collection.update_many(
            {
                "user_id": dealer_id,
                "status": {"$ne": "Cancelled"},
                "payment_status": {"$ne": "Paid"}
            },
            {
                "$set": {
                    "payment_status": "Paid",
                    "updated_at": utils.get_current_time()
                }
            }
        )
        return {
            "status": "success",
            "message": f"Successfully renewed credit for dealer {dealer_id}. Marked {result.modified_count} outstanding order(s) as Paid.",
            "modified_count": result.modified_count
        }


@router.get("/dealers", response_model=List[schemas.User])
def get_all_dealers(
    search: Optional[str] = Query(None, description="Search by first name, last name, mobile or email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    query = {"role": "Dealer"}
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"mobile_number": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
        
    dealers = list(users_collection.find(query).skip(skip).limit(limit).sort("created_at", -1))
    for dealer in dealers:
        dealer.pop("_id", None)
        
    return dealers


@router.get("/dealers/{dealer_id}/addresses", response_model=List[schemas.DealerCompanyAddressResponse])
def get_dealer_addresses(
    dealer_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    from .b2b_dealer_api import B2BDealerOperations
    return B2BDealerOperations.list_addresses(dealer_id)



@router.post("/inwards/", response_model=schemas.B2BInwardProduct, status_code=status.HTTP_201_CREATED)
def inward_product(
    inward_data: schemas.B2BInwardProductCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BInwardOperations.create_inward(inward_data, current_user)



@router.get("/inwards/cards", response_model=List[schemas.B2BSubmodelCardResponse])
def get_inward_product_cards(
    is_featured: Optional[bool] = None,
    is_new_arrival: Optional[bool] = None,
    is_best_seller: Optional[bool] = None,
    is_active: Optional[bool] = None,
    is_individual: Optional[bool] = None,
    is_carton: Optional[bool] = None,
    category_id: Optional[str] = None,
    subcategory_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    model_id: Optional[str] = None,
    submodel_id: Optional[str] = None,
    # Variant-level filters
    color: Optional[str] = None,
    size: Optional[int] = None,
    size_name: Optional[str] = None,
    chinstrap_lock: Optional[str] = None,
):
    return B2BInwardOperations.get_inward_cards(
        is_featured=is_featured,
        is_new_arrival=is_new_arrival,
        is_best_seller=is_best_seller,
        is_active=is_active,
        is_individual=is_individual,
        is_carton=is_carton,
        category_id=category_id,
        subcategory_id=subcategory_id,
        brand_id=brand_id,
        model_id=model_id,
        submodel_id=submodel_id,
        color=color,
        size=size,
        size_name=size_name,
        chinstrap_lock=chinstrap_lock,
    )

@router.get("/inwards/filters", response_model=dict)
def get_inward_filters() -> dict:
    """Return distinct filter data options present in the B2B inwarded products database.
    
    This includes unique categories, subcategories, brands, models, submodels,
    colors, sizes, and size names that have active/linked inwarded products.
    """
    return B2BInwardOperations.get_filter_options()

@router.get("/inwards/{inward_id}", response_model=schemas.B2BInwardDetailResponse)
def get_inward_product_detail(
    inward_id: str
):
    return B2BInwardOperations.get_inward_detail(inward_id)

@router.put("/inwards/{inward_id}", response_model=schemas.B2BInwardProduct)
def update_inward_product(
    inward_id: str,
    update_data: schemas.B2BInwardProductUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BInwardOperations.update_inward(inward_id, update_data)

@router.delete("/inwards/{inward_id}", response_model=dict)
def delete_inward_product(
    inward_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BInwardOperations.delete_inward(inward_id)


@router.post("/coupons/", response_model=schemas.B2BCouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    coupon_data: schemas.B2BCouponCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BCouponOperations.create_coupon(coupon_data, current_user)


@router.get("/coupons/", response_model=List[schemas.B2BCouponResponse])
def get_coupons(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BCouponOperations.get_coupons(page=page, limit=limit, search=search)


@router.get("/coupons/{coupon_id}", response_model=schemas.B2BCouponResponse)
def get_coupon(
    coupon_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BCouponOperations.get_coupon(coupon_id)


@router.put("/coupons/{coupon_id}", response_model=schemas.B2BCouponResponse)
def update_coupon(
    coupon_id: str,
    update_data: schemas.B2BCouponUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BCouponOperations.update_coupon(coupon_id, update_data)


@router.delete("/coupons/{coupon_id}", response_model=dict)
def delete_coupon(
    coupon_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BCouponOperations.delete_coupon(coupon_id)


@router.get("/limits/default", response_model=schemas.B2BDefaultLimitsResponse)
def get_default_limits(
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BLimitsOperations.get_default_limits()

@router.put("/limits/default", response_model=schemas.B2BDefaultLimitsResponse)
def update_default_limits(
    payload: schemas.B2BLimitsUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BLimitsOperations.update_default_limits(payload, current_user)

@router.put("/limits/dealer/{dealer_id}", response_model=schemas.User)
def update_dealer_limits(
    dealer_id: str,
    payload: schemas.B2BLimitsUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BLimitsOperations.update_dealer_limits(dealer_id, payload)
@router.post("/limits/dealer/{dealer_id}/renew-credit", response_model=dict)
def renew_dealer_credit(
    dealer_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BLimitsOperations.renew_dealer_credit(dealer_id)


class B2BGstSettingsOperations:

    @staticmethod
    def create_setting(setting_data: schemas.B2BGstSettingCreate, current_user: dict) -> dict:
        existing = b2b_gst_settings_collection.find_one({"state": {"$regex": f"^{setting_data.state}$", "$options": "i"}})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GST settings for state '{setting_data.state}' already exist."
            )
        
        setting_id = utils.generate_custom_id("GSTS", b2b_gst_settings_collection, "setting_id")
        setting_dict = setting_data.model_dump() if hasattr(setting_data, "model_dump") else setting_data.dict()
        setting_dict["setting_id"] = setting_id
        setting_dict["created_by"] = current_user["user_id"]
        setting_dict["created_at"] = utils.get_current_time()
        setting_dict["updated_at"] = utils.get_current_time()
        
        b2b_gst_settings_collection.insert_one(setting_dict)
        setting_dict.pop("_id", None)
        return setting_dict

    @staticmethod
    def get_settings(page: int = 1, limit: int = 50, search: str = "") -> List[dict]:
        query = {}
        if search:
            query["$or"] = [
                {"state": {"$regex": search, "$options": "i"}},
                {"setting_id": {"$regex": search, "$options": "i"}}
            ]
        skip = (page - 1) * limit
        settings = list(b2b_gst_settings_collection.find(query).skip(skip).limit(limit))
        for s in settings:
            s.pop("_id", None)
        return settings

    @staticmethod
    def get_setting(setting_id: str) -> dict:
        setting = b2b_gst_settings_collection.find_one({"setting_id": setting_id})
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GST setting with ID '{setting_id}' not found"
            )
        setting.pop("_id", None)
        return setting

    @staticmethod
    def update_setting(setting_id: str, update_data: schemas.B2BGstSettingUpdate) -> dict:
        setting = b2b_gst_settings_collection.find_one({"setting_id": setting_id})
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GST setting with ID '{setting_id}' not found"
            )
        
        update_dict = update_data.model_dump(exclude_unset=True) if hasattr(update_data, "model_dump") else update_data.dict(exclude_unset=True)
        if "state" in update_dict and update_dict["state"]:
            # Check for conflict with other states
            conflict = b2b_gst_settings_collection.find_one({
                "state": {"$regex": f"^{update_dict['state']}$", "$options": "i"},
                "setting_id": {"$ne": setting_id}
            })
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GST settings for state '{update_dict['state']}' already exist."
                )

        if update_dict:
            update_dict["updated_at"] = utils.get_current_time()
            b2b_gst_settings_collection.update_one({"setting_id": setting_id}, {"$set": update_dict})
            
        updated = b2b_gst_settings_collection.find_one({"setting_id": setting_id})
        updated.pop("_id", None)
        return updated

    @staticmethod
    def delete_setting(setting_id: str) -> dict:
        setting = b2b_gst_settings_collection.find_one({"setting_id": setting_id})
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"GST setting with ID '{setting_id}' not found"
            )
        b2b_gst_settings_collection.delete_one({"setting_id": setting_id})
        return {"status": "success", "message": f"GST setting '{setting_id}' deleted successfully"}


@router.post("/gst-settings/", response_model=schemas.B2BGstSettingResponse, status_code=status.HTTP_201_CREATED)
def create_gst_setting(
    setting_data: schemas.B2BGstSettingCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BGstSettingsOperations.create_setting(setting_data, current_user)


@router.get("/gst-settings/", response_model=List[schemas.B2BGstSettingResponse])
def get_gst_settings(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BGstSettingsOperations.get_settings(page=page, limit=limit, search=search)


@router.get("/gst-settings/{setting_id}", response_model=schemas.B2BGstSettingResponse)
def get_gst_setting(
    setting_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BGstSettingsOperations.get_setting(setting_id)


@router.put("/gst-settings/{setting_id}", response_model=schemas.B2BGstSettingResponse)
def update_gst_setting(
    setting_id: str,
    update_data: schemas.B2BGstSettingUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BGstSettingsOperations.update_setting(setting_id, update_data)


@router.delete("/gst-settings/{setting_id}", response_model=dict)
def delete_gst_setting(
    setting_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return B2BGstSettingsOperations.delete_setting(setting_id)

