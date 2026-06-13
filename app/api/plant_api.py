from fastapi import APIRouter, Depends, status, HTTPException, Query
from .. import schemas, auth, utils
from ..database import plants_collection

router = APIRouter(prefix="/api", tags=["Plants"])

class PlantOperations:
    @staticmethod
    def create_plant(plant: schemas.PlantCreate):
        plant_dict = plant.model_dump() if hasattr(plant, "model_dump") else plant.dict()
        plant_dict["plant_id"] = utils.generate_custom_id("PLT", plants_collection, "plant_id")
        plant_dict.setdefault("status", "Active")

        plants_collection.insert_one(plant_dict)
        plant_dict.pop("_id", None)
        return plant_dict

    @staticmethod
    def get_plants(page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if search:
            query["$or"] = [
                {"plant_name": {"$regex": search, "$options": "i"}},
                {"plant_address": {"$regex": search, "$options": "i"}},
                {"unit": {"$regex": search, "$options": "i"}},
                {"location_name": {"$regex": search, "$options": "i"}},
                {"city": {"$regex": search, "$options": "i"}},
                {"state": {"$regex": search, "$options": "i"}},
                {"gstin": {"$regex": search, "$options": "i"}},
                {"pincode": {"$regex": search, "$options": "i"}}
            ]
        skip = (page - 1) * limit
        plants = list(plants_collection.find(query).skip(skip).limit(limit))
        for p in plants:
            p.pop("_id", None)
        return plants

    @staticmethod
    def update_plant_status(plant_id: str, plant: schemas.PlantUpdate):
        existing_plant = plants_collection.find_one({"plant_id": plant_id})
        if not existing_plant:
            raise HTTPException(status_code=404, detail="Plant not found")

        update_dict = plant.model_dump(exclude_unset=True) if hasattr(plant, "model_dump") else plant.dict(exclude_unset=True)
        
        if "status" in update_dict and update_dict["status"]:
            allowed_statuses = ["Active", "Inactive"]
            if update_dict["status"] not in allowed_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status '{update_dict['status']}'. Allowed values: {allowed_statuses}"
                )

        if update_dict:
            plants_collection.update_one({"plant_id": plant_id}, {"$set": update_dict})

        updated_plant = plants_collection.find_one({"plant_id": plant_id})
        updated_plant.pop("_id", None)
        return updated_plant


@router.post("/plants/", response_model=schemas.Plant, status_code=status.HTTP_201_CREATED)
def create_plant(
    plant: schemas.PlantCreate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin"]))
):
    return PlantOperations.create_plant(plant)


@router.get("/plants/", response_model=list[schemas.Plant])
def get_plants(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin"]))
):
    return PlantOperations.get_plants(page=page, limit=limit, search=search)


@router.put("/plants/{plant_id}", response_model=schemas.Plant)
def update_plant_status(
    plant_id: str,
    plant: schemas.PlantUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin"]))
):
    return PlantOperations.update_plant_status(plant_id, plant)
