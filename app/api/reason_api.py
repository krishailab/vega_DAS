from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from .. import schemas, auth, utils
from ..database import reasons_collection, processes_collection

router = APIRouter(prefix="/api/reason", tags=["Reasons"])

class ReasonOperations:
    @staticmethod
    def create_reason(reason: schemas.ReasonCreate, current_user: dict):
        reason_dict = reason.model_dump() if hasattr(reason, "model_dump") else reason.dict()
        
        # Enforce process_id existence in payload
        if not reason_dict.get("process_id"):
            raise HTTPException(status_code=400, detail="Reason must be explicitly assigned a process_id.")

        # Validate that the process exists
        process = processes_collection.find_one({"process_id": reason_dict["process_id"]})
        if not process:
            raise HTTPException(status_code=404, detail=f"Assigned process_id '{reason_dict['process_id']}' not found in database.")

        reason_dict["process_name"] = process.get("name")

        # Check unique constraint of reason name per process
        if reasons_collection.find_one({"name": reason_dict["name"], "process_id": reason_dict["process_id"]}):
            raise HTTPException(status_code=400, detail=f"Reason '{reason_dict['name']}' already exists for this process")

        reason_dict["reason_id"] = utils.generate_custom_id("RSN", reasons_collection, "reason_id")
        reason_dict["created_by"] = current_user["user_id"]
        reason_dict["created_at"] = utils.get_current_time()
        
        reasons_collection.insert_one(reason_dict)
        reason_dict.pop("_id", None)
        return reason_dict

    @staticmethod
    def get_reasons(process_id: Optional[str] = None):
        query = {}
        if process_id:
            query["process_id"] = process_id
        reasons = list(reasons_collection.find(query))
        for r in reasons:
            r.pop("_id", None)
            if r.get("process_id") and not r.get("process_name"):
                process = processes_collection.find_one({"process_id": r["process_id"]})
                if process:
                    r["process_name"] = process.get("name")
        return reasons

    @staticmethod
    def delete_reason(reason_id: str, current_user: dict):
        query = {"reason_id": reason_id}
        if current_user.get("role") != "Super Admin":
            query["created_by"] = current_user["user_id"]
            
        existing = reasons_collection.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Reason not found")
            
        reasons_collection.delete_one({"reason_id": reason_id})
        return {"detail": "Reason deleted successfully"}


@router.post("/", response_model=schemas.Reason, status_code=status.HTTP_201_CREATED)
def create_reason(
    reason: schemas.ReasonCreate, 
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ReasonOperations.create_reason(reason, current_user)

@router.get("/", response_model=list[schemas.Reason])
def get_reasons(
    process_id: Optional[str] = Query(None, description="Filter reasons by process_id")
):
    return ReasonOperations.get_reasons(process_id)

@router.delete("/{reason_id}")
def delete_reason(
    reason_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return ReasonOperations.delete_reason(reason_id, current_user)
