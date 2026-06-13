from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Query
from typing import List, Optional
import os
import shutil
from .. import schemas, auth, utils
from ..database import (
    assets_collection,
    asset_categories_collection,
    asset_subcategories_collection,
    asset_assignments_collection,
    asset_submissions_collection,
    users_collection
)

router = APIRouter(prefix="/assets", tags=["Assets"])


def _enrich_asset(asset: dict) -> dict:
    """Add is_assigned flag by checking the assignments collection."""
    asset.pop("_id", None)
    active_assignment = asset_assignments_collection.find_one(
        {"asset_id": asset["asset_id"], "is_active": True}
    )
    asset["is_assigned"] = active_assignment is not None
    return asset


# ─────────────────────────────────────────────────────────────
# CATEGORY OPERATIONS
# ─────────────────────────────────────────────────────────────

class AssetOperations:


    @staticmethod
    def get_dashboard(current_user: dict, master_admin_id: Optional[str] = None):
        query = {}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]
        elif current_user["role"] in ["Super Admin", "B2B Admin"] and master_admin_id:
            query["master_admin_id"] = master_admin_id
        
        # 1. Status Summary
        total_assets = assets_collection.count_documents(query)
        
        # Get all asset IDs for this user to filter assignments/submissions
        user_assets = list(assets_collection.find(query, {"asset_id": 1}))
        user_asset_ids = [a["asset_id"] for a in user_assets]
        
        assigned_count = asset_assignments_collection.count_documents({
            "is_active": True,
            "asset_id": {"$in": user_asset_ids}
        })
        
        status_summary = {
            "total": total_assets,
            "assigned": assigned_count,
            "available": max(0, total_assets - assigned_count)
        }

        # 2. Category Summary
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$category_id",
                "category_name": {"$first": "$category_name"},
                "count": {"$sum": 1}
            }}
        ]
        categories_data = list(assets_collection.aggregate(pipeline))
        category_summary = [
            {
                "category_id": c["_id"],
                "category_name": c["category_name"] or "Unknown",
                "count": c["count"]
            } for c in categories_data
        ]

        # 3. Warranty Summary
        warranty_count = assets_collection.count_documents({**query, "is_warranty": True})
        guarantee_count = assets_collection.count_documents({**query, "is_guarantee": True})
        no_warranty_count = total_assets - (warranty_count + guarantee_count)

        warranty_summary = {
            "under_warranty": warranty_count,
            "under_guarantee": guarantee_count,
            "no_warranty": max(0, no_warranty_count)
        }

        # 4. Recent Submissions
        recent_subs = list(asset_submissions_collection.find(
            {"asset_id": {"$in": user_asset_ids}}
        ).sort("submitted_at", -1).limit(5))
        
        for s in recent_subs:
            s.pop("_id", None)

        return {
            "status_summary": status_summary,
            "category_summary": category_summary,
            "warranty_summary": warranty_summary,
            "recent_submissions": recent_subs
        }

    @staticmethod
    def create_category(category: schemas.AssetCategoryCreate, current_user: dict):
        if asset_categories_collection.find_one({"name": category.name}):
            raise HTTPException(status_code=400, detail="Category already exists")

        category_dict = category.model_dump()
        category_dict["category_id"] = utils.generate_custom_id("CAT", asset_categories_collection, "category_id")
        category_dict["created_by"] = current_user["user_id"]
        category_dict["created_at"] = utils.get_current_time()

        asset_categories_collection.insert_one(category_dict)
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
        skip = (page - 1) * limit
        categories = list(asset_categories_collection.find(query).skip(skip).limit(limit))
        for c in categories:
            c.pop("_id", None)
        return categories

    @staticmethod
    def create_subcategory(subcategory: schemas.AssetSubCategoryCreate, current_user: dict):
        # Validate category_id
        category = asset_categories_collection.find_one({"category_id": subcategory.category_id})
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        if asset_subcategories_collection.find_one({
            "name": subcategory.name, 
            "category_id": subcategory.category_id
        }):
            raise HTTPException(status_code=400, detail="SubCategory already exists in this category")

        sub_dict = subcategory.model_dump()
        sub_dict["subcategory_id"] = utils.generate_custom_id("SUB", asset_subcategories_collection, "subcategory_id")
        sub_dict["category_name"] = category.get("name")
        sub_dict["created_by"] = current_user["user_id"]
        sub_dict["created_at"] = utils.get_current_time()

        asset_subcategories_collection.insert_one(sub_dict)
        sub_dict.pop("_id", None)
        return sub_dict

    @staticmethod
    def get_subcategories(category_id: Optional[str] = None, page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if category_id:
            query["category_id"] = category_id
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"subcategory_id": {"$regex": search, "$options": "i"}},
                {"category_name": {"$regex": search, "$options": "i"}}
            ]
        skip = (page - 1) * limit
        subcategories = list(asset_subcategories_collection.find(query).skip(skip).limit(limit))
        for s in subcategories:
            s.pop("_id", None)
        return subcategories

    # ─── ASSET CRUD ───────────────────────────────────────────

    @staticmethod
    def create_asset(name, asset_no, model, brand, purchase_date, cost, category_id, subcategory_id, is_warranty, is_guarantee, warranty_expiry_date, color, guarantee_date, expire_date, comment, status, maintenance_period, invoice_pdf, images, current_user):
        # --- Validation ---
        has_flag = is_warranty or is_guarantee
        has_date = bool(warranty_expiry_date)
        if has_flag and not has_date:
            raise HTTPException(status_code=400, detail="warranty_expiry_date is required if is_warranty or is_guarantee is true")
        if has_date and not has_flag:
            raise HTTPException(status_code=400, detail="is_warranty or is_guarantee must be true if warranty_expiry_date is provided")

        asset_id = utils.generate_custom_id("ASS", assets_collection, "asset_id", digits=6)
        master_admin_id = current_user.get("master_admin_id") or current_user["user_id"]
        master_admin_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

        # Resolve category and subcategory names
        cat_obj = asset_categories_collection.find_one({"category_id": category_id})
        if not cat_obj:
            raise HTTPException(status_code=400, detail="Invalid Category ID")
        cat_name = cat_obj["name"]
        
        sub_name = None
        if subcategory_id:
            sub_obj = asset_subcategories_collection.find_one({"subcategory_id": subcategory_id})
            if not sub_obj:
                raise HTTPException(status_code=400, detail="Invalid SubCategory ID")
            sub_name = sub_obj["name"]

        base_dir = os.path.join("qrcodes", master_admin_id, "Assets", asset_id)
        os.makedirs(base_dir, exist_ok=True)

        invoice_path = None
        if invoice_pdf and invoice_pdf.filename:
            ext = os.path.splitext(invoice_pdf.filename)[1] or ".pdf"
            invoice_path = os.path.join(base_dir, f"invoice{ext}")
            with open(invoice_path, "wb") as buf:
                shutil.copyfileobj(invoice_pdf.file, buf)

        image_paths = []
        for i, img in enumerate(images[:10]):
            if not img.filename:
                continue
            ext = os.path.splitext(img.filename)[1] or ".jpg"
            img_path = os.path.join(base_dir, f"image_{i}{ext}")
            with open(img_path, "wb") as buf:
                shutil.copyfileobj(img.file, buf)
            image_paths.append(img_path)

        asset_dict = {
            "asset_id": asset_id,
            "name": name,
            "asset_no": asset_no,
            "model": model,
            "brand": brand,
            "purchase_date": purchase_date,
            "cost": cost,
            "category_id": category_id,
            "category_name": cat_name,
            "subcategory_id": subcategory_id,
            "subcategory_name": sub_name,
            "is_warranty": is_warranty,
            "is_guarantee": is_guarantee,
            "warranty_expiry_date": warranty_expiry_date,
            "color": color,
            "guarantee_date": guarantee_date,
            "expire_date": expire_date,
            "comment": comment,
            "status": status or "Active",
            "maintenance_period": maintenance_period,
            "invoice_pdf": invoice_path,
            "images": image_paths,
            "master_admin_id": master_admin_id,
            "master_admin_name": master_admin_name,
            "created_at": utils.get_current_time()
        }

        assets_collection.insert_one(asset_dict)
        return _enrich_asset(asset_dict)

    @staticmethod
    def get_assets(current_user: dict, 
                   category_id: Optional[str] = None, 
                   subcategory_id: Optional[str] = None, 
                   brand: Optional[str] = None, 
                   name: Optional[str] = None,
                   asset_no: Optional[str] = None,
                   model: Optional[str] = None,
                   status: Optional[str] = None,
                   is_warranty: Optional[bool] = None,
                   is_guarantee: Optional[bool] = None,
                   search: Optional[str] = None,
                   master_admin_id: Optional[str] = None,
                   page: int = 1,
                   limit: int = 50):
        query = {}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]
        elif current_user["role"] in ["Super Admin", "B2B Admin"] and master_admin_id:
            query["master_admin_id"] = master_admin_id
        
        # Dynamic filtering for exact matches
        filters = {
            "category_id": category_id,
            "subcategory_id": subcategory_id,
            "brand": brand,
            "name": name,
            "asset_no": asset_no,
            "model": model,
            "status": status,
            "is_warranty": is_warranty,
            "is_guarantee": is_guarantee
        }
        for key, value in filters.items():
            if value is not None:
                query[key] = value
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"asset_no": {"$regex": search, "$options": "i"}},
                {"model": {"$regex": search, "$options": "i"}},
                {"brand": {"$regex": search, "$options": "i"}},
                {"category_name": {"$regex": search, "$options": "i"}},
                {"subcategory_name": {"$regex": search, "$options": "i"}}
            ]

        skip = (page - 1) * limit
        assets = list(assets_collection.find(query).skip(skip).limit(limit))
        return [_enrich_asset(a) for a in assets]

    @staticmethod
    def update_asset(asset_id, name, asset_no, model, brand, purchase_date, cost, category_id, subcategory_id, is_warranty, is_guarantee, warranty_expiry_date, color, guarantee_date, expire_date, comment, status, maintenance_period, invoice_pdf, new_images, current_user):
        query = {"asset_id": asset_id}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]

        existing = assets_collection.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Asset not found")

        # --- Validation (for updates, check combination of new values and existing values) ---
        new_is_warranty = is_warranty if is_warranty is not None else existing.get("is_warranty", False)
        new_is_guarantee = is_guarantee if is_guarantee is not None else existing.get("is_guarantee", False)
        new_has_flag = new_is_warranty or new_is_guarantee
        
        # If date is in update, use it; otherwise use existing date (if any)
        new_date = warranty_expiry_date if warranty_expiry_date is not None else existing.get("warranty_expiry_date")
        new_has_date = bool(new_date)

        if new_has_flag and not new_has_date:
            raise HTTPException(status_code=400, detail="warranty_expiry_date is required if is_warranty or is_guarantee is true")
        if new_has_date and not new_has_flag:
            raise HTTPException(status_code=400, detail="is_warranty or is_guarantee must be true if warranty_expiry_date is provided")


        update_data = {}
        if name: update_data["name"] = name
        if asset_no: update_data["asset_no"] = asset_no
        if model: update_data["model"] = model
        if brand: update_data["brand"] = brand
        if purchase_date: update_data["purchase_date"] = purchase_date
        if cost is not None: update_data["cost"] = cost
        if category_id:
            update_data["category_id"] = category_id
            cat_obj = asset_categories_collection.find_one({"category_id": category_id})
            if not cat_obj:
                raise HTTPException(status_code=400, detail="Invalid Category ID")
            update_data["category_name"] = cat_obj["name"]
        
        if subcategory_id:
            update_data["subcategory_id"] = subcategory_id
            sub_obj = asset_subcategories_collection.find_one({"subcategory_id": subcategory_id})
            if not sub_obj:
                raise HTTPException(status_code=400, detail="Invalid SubCategory ID")
            update_data["subcategory_name"] = sub_obj["name"]
        
        if is_warranty is not None: update_data["is_warranty"] = is_warranty
        if is_guarantee is not None: update_data["is_guarantee"] = is_guarantee
        if warranty_expiry_date: update_data["warranty_expiry_date"] = warranty_expiry_date
        if color is not None: update_data["color"] = color
        if guarantee_date is not None: update_data["guarantee_date"] = guarantee_date
        if expire_date is not None: update_data["expire_date"] = expire_date
        if comment: update_data["comment"] = comment
        if status: update_data["status"] = status
        if maintenance_period: update_data["maintenance_period"] = maintenance_period

        base_dir = os.path.join("qrcodes", existing["master_admin_id"], "Assets", asset_id)
        os.makedirs(base_dir, exist_ok=True)

        if invoice_pdf and invoice_pdf.filename:
            ext = os.path.splitext(invoice_pdf.filename)[1] or ".pdf"
            invoice_path = os.path.join(base_dir, f"invoice{ext}")
            with open(invoice_path, "wb") as buf:
                shutil.copyfileobj(invoice_pdf.file, buf)
            update_data["invoice_pdf"] = invoice_path

        if new_images:
            image_paths = existing.get("images", [])
            for img in new_images:
                if len(image_paths) >= 10 or not img.filename:
                    break
                ext = os.path.splitext(img.filename)[1] or ".jpg"
                img_path = os.path.join(base_dir, f"image_{len(image_paths)}{ext}")
                with open(img_path, "wb") as buf:
                    shutil.copyfileobj(img.file, buf)
                image_paths.append(img_path)
            update_data["images"] = image_paths

        if update_data:
            assets_collection.update_one({"asset_id": asset_id}, {"$set": update_data})

        updated = assets_collection.find_one({"asset_id": asset_id})
        return _enrich_asset(updated)

    # ─── ASSIGNMENT ───────────────────────────────────────────

    @staticmethod
    def assign_asset(asset_id: str, user_id: str, notes: Optional[str], current_user: dict):
        query = {"asset_id": asset_id}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]
        asset = assets_collection.find_one(query)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Block if already actively assigned and not submitted
        active = asset_assignments_collection.find_one({"asset_id": asset_id, "is_active": True})
        if active:
            raise HTTPException(
                status_code=400,
                detail="This asset is already assigned. Please submit it before reassigning."
            )

        target_user = users_collection.find_one({"user_id": user_id})
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        if target_user["role"] not in ["Reader", "Linker", "Inspector"]:
            raise HTTPException(status_code=400, detail="Assets can only be assigned to sub-users (Reader, Linker, Inspector)")

        now = utils.get_current_time()
        assignment = {
            "assignment_id": utils.generate_custom_id("ASN", asset_assignments_collection, "assignment_id"),
            "asset_id": asset_id,
            "asset_name": asset.get("name"),
            "user_id": user_id,
            "user_name": f"{target_user.get('first_name', '')} {target_user.get('last_name', '')}".strip(),
            "role": target_user.get("role"),
            "assigned_by": current_user["user_id"],
            "assigned_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
            "assigned_at": now,
            "notes": notes or "",
            "is_active": True
        }

        asset_assignments_collection.insert_one(assignment)
        assignment.pop("_id", None)
        return assignment

    @staticmethod
    def unassign_asset(asset_id: str, user_id: str, current_user: dict):
        query = {"asset_id": asset_id}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]
        asset = assets_collection.find_one(query)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        result = asset_assignments_collection.update_one(
            {"asset_id": asset_id, "user_id": user_id, "is_active": True},
            {"$set": {"is_active": False, "unassigned_at": utils.get_current_time()}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="No active assignment found for this user on this asset")

        return {"detail": "Assignment removed successfully", "asset_id": asset_id, "user_id": user_id}

    @staticmethod
    def get_asset_assignments(asset_id: str, current_user: dict):
        """All assignments (active and inactive) for an asset."""
        query = {"asset_id": asset_id}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]
        asset = assets_collection.find_one(query)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        assignments = list(asset_assignments_collection.find({"asset_id": asset_id}))
        for a in assignments:
            a.pop("_id", None)
        return assignments

    # ─── SUBMISSION ───────────────────────────────────────────

    @staticmethod
    def submit_asset(asset_id: str, status: str, condition: Optional[str], remarks: Optional[str], current_user: dict):
        if status not in ["RECEIVED", "RETURNED"]:
            raise HTTPException(status_code=400, detail="Status must be 'RECEIVED' or 'RETURNED'")

        query = {"asset_id": asset_id}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]
        asset = assets_collection.find_one(query)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Find the active assignment for this asset
        active_assignment = asset_assignments_collection.find_one({"asset_id": asset_id, "is_active": True})
        if not active_assignment:
            raise HTTPException(status_code=400, detail="No active assignment found for this asset")

        now = utils.get_current_time()
        submission = {
            "submission_id": utils.generate_custom_id("SUB", asset_submissions_collection, "submission_id"),
            "asset_id": asset_id,
            "asset_name": asset.get("name"),
            "assignment_id": active_assignment["assignment_id"],
            "assigned_user_id": active_assignment["user_id"],
            "assigned_user_name": active_assignment["user_name"],
            "status": status,
            "condition": condition or "Good",
            "remarks": remarks or "",
            "submitted_by": current_user["user_id"],
            "submitted_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
            "submitted_at": now
        }

        asset_submissions_collection.insert_one(submission)

        # Mark assignment as inactive after submission
        asset_assignments_collection.update_one(
            {"assignment_id": active_assignment["assignment_id"]},
            {"$set": {"is_active": False, "submitted_at": now}}
        )

        submission.pop("_id", None)
        return submission


    @staticmethod
    def get_active_assigned_assets(current_user: dict, master_admin_id: Optional[str] = None):
        """Assets with an active (unsubmitted) assignment, with assigned user info."""
        active_assignments = list(asset_assignments_collection.find({"is_active": True}))

        result = []
        for assignment in active_assignments:
            assignment.pop("_id", None)
            query = {"asset_id": assignment["asset_id"]}
            if current_user["role"] == "Master Admin":
                query["master_admin_id"] = current_user["user_id"]
            elif current_user["role"] in ["Super Admin", "B2B Admin"] and master_admin_id:
                query["master_admin_id"] = master_admin_id
            asset = assets_collection.find_one(query)
            if not asset:
                continue
            asset.pop("_id", None)
            asset["is_assigned"] = True
            asset["assigned_to"] = {
                "user_id": assignment.get("user_id"),
                "user_name": assignment.get("user_name"),
                "role": assignment.get("role"),
                "assigned_at": assignment.get("assigned_at"),
                "notes": assignment.get("notes"),
                "assignment_id": assignment.get("assignment_id")
            }
            result.append(asset)
        return result

    @staticmethod
    def get_submitted_assets(current_user: dict, master_admin_id: Optional[str] = None):
        """Assets that have at least one submission record."""
        sub_query = {}
        asset_query = {}
        if current_user["role"] == "Master Admin":
            sub_query["submitted_by"] = current_user["user_id"]
            asset_query["master_admin_id"] = current_user["user_id"]
        elif current_user["role"] in ["Super Admin", "B2B Admin"] and master_admin_id:
            asset_query["master_admin_id"] = master_admin_id

        submitted_asset_ids = asset_submissions_collection.distinct(
            "asset_id", sub_query
        )
        asset_query["asset_id"] = {"$in": submitted_asset_ids}
        assets = list(assets_collection.find(asset_query))
        result = []
        for a in assets:
            a.pop("_id", None)
            # Attach latest submission details
            latest_sub = asset_submissions_collection.find_one(
                {"asset_id": a["asset_id"]},
                sort=[("submitted_at", -1)]
            )
            if latest_sub:
                latest_sub.pop("_id", None)
            a["latest_submission"] = latest_sub
            a["is_assigned"] = False
            result.append(a)
        return result

    @staticmethod
    def get_my_assets(current_user: dict):
        """Sub-user: all assets actively assigned to them."""
        active_assignments = list(asset_assignments_collection.find(
            {"user_id": current_user["user_id"], "is_active": True}
        ))
        result = []
        for assignment in active_assignments:
            assignment.pop("_id", None)
            asset = assets_collection.find_one({"asset_id": assignment["asset_id"]})
            if asset:
                asset.pop("_id", None)
                asset["assignment"] = assignment
                asset["is_assigned"] = True
                result.append(asset)
        return result


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=schemas.AssetDashboard)
def get_asset_dashboard(
    master_admin_id: Optional[str] = None,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    return AssetOperations.get_dashboard(current_user, master_admin_id)

@router.post("/categories", response_model=schemas.AssetCategory)
def create_category(
    category: schemas.AssetCategoryCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return AssetOperations.create_category(category, current_user)

@router.get("/categories", response_model=List[schemas.AssetCategory])
def get_categories(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.get_current_user)
):
    return AssetOperations.get_categories(page=page, limit=limit, search=search)

@router.post("/subcategories", response_model=schemas.AssetSubCategory)
def create_subcategory(
    subcategory: schemas.AssetSubCategoryCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return AssetOperations.create_subcategory(subcategory, current_user)

@router.get("/subcategories", response_model=List[schemas.AssetSubCategory])
def get_subcategories(
    category_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.get_current_user)
):
    return AssetOperations.get_subcategories(category_id, page=page, limit=limit, search=search)

@router.get("/my-assets")
def get_my_assets(
    current_user: dict = Depends(auth.RoleChecker(["Reader", "Linker", "Inspector"]))
):
    """Sub-users: view all assets actively assigned to you."""
    return AssetOperations.get_my_assets(current_user)

@router.get("/active-assigned")
def get_active_assigned_assets(
    master_admin_id: Optional[str] = None,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    """Assets actively assigned to sub-users and not yet submitted."""
    return AssetOperations.get_active_assigned_assets(current_user, master_admin_id)

@router.get("/submitted")
def get_submitted_assets(
    master_admin_id: Optional[str] = None,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    """Assets that have been submitted (RECEIVED or RETURNED)."""
    return AssetOperations.get_submitted_assets(current_user, master_admin_id)

@router.post("/", response_model=schemas.Asset)
def create_asset(
    name: str = Form(...),
    asset_no: str = Form(...),
    model: str = Form(...),
    brand: str = Form(...),
    purchase_date: str = Form(...),
    cost: float = Form(...),
    category_id: str = Form(..., alias="category_id", description="ID of the asset category"),
    subcategory_id: Optional[str] = Form(None, alias="subcategory_id", description="ID of the asset subcategory"),
    is_warranty: Optional[bool] = Form(None, description="Whether the asset has a warranty"),
    is_guarantee: Optional[bool] = Form(None, description="Whether the asset has a guarantee"),
    warranty_expiry_date: Optional[str] = Form(None, description="Expiry date of warranty/guarantee"),
    color: Optional[str] = Form(None),
    guarantee_date: Optional[str] = Form(None),
    expire_date: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    status: str = Form("Active", description="Active or Inactive"),
    maintenance_period: Optional[str] = Form(None, description="e.g. 1 month, 6 month"),
    invoice_pdf: Optional[UploadFile] = File(None),
    images: list[UploadFile] = File([]),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    return AssetOperations.create_asset(name, asset_no, model, brand, purchase_date, cost, category_id, subcategory_id, is_warranty, is_guarantee, warranty_expiry_date, color, guarantee_date, expire_date, comment, status, maintenance_period, invoice_pdf, images, current_user)

@router.get("/")
def get_assets(
    category_id: Optional[str] = None,
    subcategory_id: Optional[str] = None,
    brand: Optional[str] = None,
    name: Optional[str] = None,
    asset_no: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
    is_warranty: Optional[bool] = None,
    is_guarantee: Optional[bool] = None,
    search: Optional[str] = None,
    master_admin_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    return AssetOperations.get_assets(
        current_user, category_id, subcategory_id, brand, 
        name, asset_no, model, status, is_warranty, is_guarantee, search, master_admin_id,
        page=page, limit=limit
    )

@router.post("/{asset_id}/assign")
def assign_asset(
    asset_id: str,
    user_id: str = Form(..., description="User ID of the sub-user to assign"),
    notes: Optional[str] = Form(None),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    return AssetOperations.assign_asset(asset_id, user_id, notes, current_user)

@router.post("/{asset_id}/unassign")
def unassign_asset(
    asset_id: str,
    user_id: str = Form(..., description="User ID to remove assignment for"),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    return AssetOperations.unassign_asset(asset_id, user_id, current_user)

@router.get("/{asset_id}/assignments")
def get_asset_assignments(
    asset_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    """All assignment history for an asset."""
    return AssetOperations.get_asset_assignments(asset_id, current_user)

@router.post("/{asset_id}/submit")
def submit_asset(
    asset_id: str,
    status: str = Form(..., description="RECEIVED or RETURNED"),
    condition: Optional[str] = Form(None, description="Good / Fair / Poor / Damaged"),
    remarks: Optional[str] = Form(None),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    """Submit or return an assigned asset. Creates a record in submissions collection."""
    return AssetOperations.submit_asset(asset_id, status, condition, remarks, current_user)

@router.put("/{asset_id}")
def update_asset(
    asset_id: str,
    name: Optional[str] = Form(None),
    asset_no: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    brand: Optional[str] = Form(None),
    purchase_date: Optional[str] = Form(None),
    cost: Optional[float] = Form(None),
    category_id: Optional[str] = Form(None, alias="category_id"),
    subcategory_id: Optional[str] = Form(None, alias="subcategory_id"),
    is_warranty: Optional[bool] = Form(None),
    is_guarantee: Optional[bool] = Form(None),
    warranty_expiry_date: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    guarantee_date: Optional[str] = Form(None),
    expire_date: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    maintenance_period: Optional[str] = Form(None),
    invoice_pdf: Optional[UploadFile] = File(None),
    new_images: list[UploadFile] = File([]),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin", "B2B Admin"]))
):
    # Handle is_guarantee as Form parameter explicitly to be safe
    return AssetOperations.update_asset(asset_id, name, asset_no, model, brand, purchase_date, cost, category_id, subcategory_id, is_warranty, is_guarantee, warranty_expiry_date, color, guarantee_date, expire_date, comment, status, maintenance_period, invoice_pdf, new_images, current_user)
