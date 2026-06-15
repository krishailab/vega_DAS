from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid
from .. import schemas, auth, utils
from ..database import shifts_collection

router = APIRouter(prefix="/shifts", tags=["Shifts"])

class ShiftOperations:
    @staticmethod
    def create_shift(shift: schemas.ShiftCreate, current_user: dict):
        if shifts_collection.find_one({"name": shift.name, "master_admin_email": current_user["email"]}):
            raise HTTPException(status_code=400, detail="Shift already registered for this Master Admin")
        
        shift_dict = shift.model_dump() if hasattr(shift, "model_dump") else shift.dict()
        shift_dict["start_time"] = shift.start_time.strftime("%H:%M:%S")
        shift_dict["end_time"] = shift.end_time.strftime("%H:%M:%S")
        shift_dict["shift_id"] = utils.generate_custom_id("SHT", shifts_collection, "shift_id")
        shift_dict["master_admin_id"] = current_user["user_id"]
        
        shifts_collection.insert_one(shift_dict)
        shift_dict.pop("_id", None)
        return shift_dict

    @staticmethod
    def get_shifts(master_admin_id: str, page: int = 1, limit: int = 50, search: str = ""):
        query = {"master_admin_id": master_admin_id}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"shift_id": {"$regex": search, "$options": "i"}}
            ]
        total_count = shifts_collection.count_documents(query)
        import math
        total_pages = math.ceil(total_count / limit) if limit > 0 else 0
        skip = (page - 1) * limit
        shifts = list(shifts_collection.find(query).skip(skip).limit(limit))
        for s in shifts:
            s.pop("_id", None)
        return {
            "shifts": shifts,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def update_shift(shift_id: str, shift: schemas.ShiftUpdate, current_user: dict):
        existing = shifts_collection.find_one({"shift_id": shift_id, "master_admin_id": current_user["user_id"]})
        if not existing:
            raise HTTPException(status_code=404, detail="Shift not found")
            
        update_data = shift.model_dump(exclude_unset=True) if hasattr(shift, "model_dump") else shift.dict(exclude_unset=True)
        if "start_time" in update_data:
            update_data["start_time"] = shift.start_time.strftime("%H:%M:%S")
        if "end_time" in update_data:
            update_data["end_time"] = shift.end_time.strftime("%H:%M:%S")
            
        if update_data:
            shifts_collection.update_one({"shift_id": shift_id}, {"$set": update_data})
        
        updated = shifts_collection.find_one({"shift_id": shift_id})
        updated.pop("_id", None)
        return updated

    @staticmethod
    def delete_shift(shift_id: str, current_user: dict):
        existing = shifts_collection.find_one({"shift_id": shift_id, "master_admin_id": current_user["user_id"]})
        if not existing:
            raise HTTPException(status_code=404, detail="Shift not found")
            
        shifts_collection.delete_one({"shift_id": shift_id})
        return {"detail": "Shift deleted successfully"}

@router.post("/", response_model=schemas.Shift, status_code=status.HTTP_201_CREATED)
def create_shift(
    shift: schemas.ShiftCreate, 
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return ShiftOperations.create_shift(shift, current_user)

@router.get("/", response_model=dict)
def get_shifts(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return ShiftOperations.get_shifts(current_user["user_id"], page=page, limit=limit, search=search)

@router.put("/{shift_id}", response_model=schemas.Shift)
def update_shift(
    shift_id: str,
    shift: schemas.ShiftUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return ShiftOperations.update_shift(shift_id, shift, current_user)

@router.delete("/{shift_id}")
def delete_shift(
    shift_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return ShiftOperations.delete_shift(shift_id, current_user)
