from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from .. import schemas, auth, utils
from ..database import processes_collection, parts_collection

router = APIRouter(prefix="/api/process", tags=["Processes"])

class ProcessOperations:
    @staticmethod
    def get_processes(current_user: dict, part_id: Optional[str] = None, page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        
        # Enforce role scoping, but respect part_id parameter if user has permission
        if current_user.get("role") != "Super Admin":
            user_part_id = current_user.get("part_id")
            if user_part_id:
                # Constrain to their assigned part_id (or parameter if matches)
                if part_id and part_id != user_part_id:
                    raise HTTPException(status_code=403, detail="You do not have access to view processes for this part.")
                query["part_id"] = user_part_id
            else:
                query["created_by"] = current_user["user_id"]
                if part_id:
                    query["part_id"] = part_id
        else:
            if part_id:
                query["part_id"] = part_id

        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"process_id": {"$regex": search, "$options": "i"}},
                {"part_name": {"$regex": search, "$options": "i"}}
            ]

        total_count = processes_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        processes = list(processes_collection.find(query).skip(skip).limit(limit))
        for p in processes:
            p.pop("_id", None)
            if p.get("part_id") and not p.get("part_name"):
                # Backwards compatible part name resolution
                part = parts_collection.find_one({"part_id": p["part_id"]})
                if part:
                    p["part_name"] = part.get("name")
        return {
            "processes": processes,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }


@router.get("/", response_model=dict)
def get_processes(
    part_id: Optional[str] = Query(None, description="Filter processes by part_id"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ProcessOperations.get_processes(current_user, part_id, page=page, limit=limit, search=search)
