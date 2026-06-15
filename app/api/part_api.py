from fastapi import APIRouter, Depends, status, HTTPException, Query
import uuid
from datetime import datetime
from .. import schemas, auth, utils
from ..database import parts_collection, users_collection

router = APIRouter(prefix="/api", tags=["Parts"])

class PartOperations:
    @staticmethod
    def create_part(part: schemas.PartCreate, current_user: dict):
        part_dict = part.model_dump() if hasattr(part, "model_dump") else part.dict()
        part_id = utils.generate_custom_id("PTR", parts_collection, "part_id")
        part_dict["part_id"] = part_id
        
        # Validate category_id if provided
        if part_dict.get("category_id"):
            from ..database import product_categories_collection
            cat = product_categories_collection.find_one({"category_id": part_dict["category_id"]})
            if not cat:
                raise HTTPException(status_code=400, detail=f"Category ID '{part_dict['category_id']}' does not exist.")
            part_dict["category_name"] = cat.get("name")

        # Extract process names from processes list and discard list on DB save
        processes_list = part_dict.get("processes")
        if not processes_list:
            processes_list = [part_dict.get("name")] if part_dict.get("name") else []
        elif not isinstance(processes_list, list):
            processes_list = [processes_list]
        
        parts_collection.insert_one(part_dict)
        
        # Auto-create the process entries in processes_collection
        from ..database import processes_collection
        for idx, p_name in enumerate(processes_list):
            if not p_name.strip():
                continue
            
            # Avoid creating duplicates if a process with this name already exists for this part
            existing = processes_collection.find_one({"name": p_name.strip(), "part_id": part_id})
            if existing:
                # Update existing step index to keep it correct
                processes_collection.update_one(
                    {"process_id": existing["process_id"]},
                    {"$set": {"step": idx + 1}}
                )
                continue
                
            process_id = utils.generate_custom_id("PRO", processes_collection, "process_id")
            processes_collection.insert_one({
                "process_id": process_id,
                "name": p_name.strip(),
                "part_id": part_id,
                "part_name": part_dict.get("name"),
                "step": idx + 1,
                "created_by": current_user["user_id"],
                "created_at": utils.get_current_time()
            })
            
        part_dict.pop("_id", None)
        return part_dict

    @staticmethod
    def get_parts(page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"part_id": {"$regex": search, "$options": "i"}},
                {"category_name": {"$regex": search, "$options": "i"}}
            ]
        total_count = parts_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        parts = list(parts_collection.find(query).skip(skip).limit(limit))
        for p in parts:
            p.pop("_id", None)
        return {
            "parts": parts,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_part(part_id: str, part: schemas.PartUpdate, current_user: dict):
        existing_part = parts_collection.find_one({"part_id": part_id})
        if not existing_part:
            raise HTTPException(status_code=404, detail="Part not found")
            
        update_data = part.model_dump(exclude_unset=True) if hasattr(part, "model_dump") else part.dict(exclude_unset=True)
        processes_list = update_data.get("processes")
        
        # Validate category_id if provided
        if "category_id" in update_data:
            if update_data["category_id"]:
                from ..database import product_categories_collection
                cat = product_categories_collection.find_one({"category_id": update_data["category_id"]})
                if not cat:
                    raise HTTPException(status_code=400, detail=f"Category ID '{update_data['category_id']}' does not exist.")
                update_data["category_name"] = cat.get("name")
            else:
                update_data["category_name"] = None

        if update_data:
            parts_collection.update_one({"part_id": part_id}, {"$set": update_data})

        # Sync process entries in processes_collection if processes list was updated
        if processes_list is not None:
            from ..database import processes_collection
            
            # Sync and order new process entries passed in the update payload
            for idx, p_name in enumerate(processes_list):
                if not p_name.strip():
                    continue
                existing = processes_collection.find_one({"name": p_name.strip(), "part_id": part_id})
                if existing:
                    processes_collection.update_one(
                        {"process_id": existing["process_id"]},
                        {"$set": {"step": idx + 1}}
                    )
                    continue
                    
                process_id = utils.generate_custom_id("PRO", processes_collection, "process_id")
                processes_collection.insert_one({
                    "process_id": process_id,
                    "name": p_name.strip(),
                    "part_id": part_id,
                    "part_name": update_data.get("name") or existing_part.get("name"),
                    "step": idx + 1,
                    "created_by": current_user["user_id"],
                    "created_at": utils.get_current_time()
                })
        
        updated_part = parts_collection.find_one({"part_id": part_id})
        updated_part.pop("_id", None)
        return updated_part

    @staticmethod
    def delete_part(part_id: str):
        existing_part = parts_collection.find_one({"part_id": part_id})
        if not existing_part:
            raise HTTPException(status_code=404, detail="Part not found")
        
        parts_collection.delete_one({"part_id": part_id})
        # Delete associated processes as well to keep data clean
        from ..database import processes_collection
        processes_collection.delete_many({"part_id": part_id})
        
        return {"detail": "Part deleted successfully"}

@router.post("/create-part/", response_model=schemas.Part, status_code=status.HTTP_201_CREATED)
def create_part(
    part: schemas.PartCreate, 
    current_user: dict = Depends(auth.RoleChecker(["Super Admin"]))
):
    return PartOperations.create_part(part, current_user)

@router.get("/parts/", response_model=dict)
def get_parts(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin"]))
):
    return PartOperations.get_parts(page=page, limit=limit, search=search)

@router.put("/parts/{part_id}", response_model=schemas.Part)
def update_part(
    part_id: str,
    part: schemas.PartUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin"]))
):
    return PartOperations.update_part(part_id, part, current_user)

@router.delete("/parts/{part_id}")
def delete_part(
    part_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin"]))
):
    return PartOperations.delete_part(part_id)
