from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid
from datetime import datetime, timedelta
from .. import schemas, auth, utils
from ..database import users_collection, parts_collection, stations_collection, shifts_collection, plants_collection, processes_collection

router = APIRouter(prefix="/users", tags=["Users"])

class UserOperations:
    @staticmethod
    def _generate_user_login_qrcode(user_id: str, mobile_number: str, plain_password: str, current_user: dict, user_data: dict = None) -> str:
        qr_data = f"{mobile_number or ''};{plain_password or ''}"
        owner_id = (
            (user_data or {}).get("master_admin_id")
            or current_user.get("user_id")
            or "system"
        )
        return utils.generate_qr_file(qr_data, owner_id, "User", user_id)

    @staticmethod
    def _enrich_user(user, include_password=False):
        if not user:
            return None
        user.pop("_id", None)
        if not include_password:
            user.pop("password", None)
        
        # Enrich Station Details
        station_id = user.get("assigned_station_id")
        if station_id:
            station = stations_collection.find_one({"station_id": station_id})
            if station:
                if not user.get("assigned_station_name"):
                    user["assigned_station_name"] = station.get("name", "Unknown Station")
                if not user.get("linker_capacity"):
                    user["linker_capacity"] = station.get("linker_capacity")
                if not user.get("global_qr_number") and station.get("global_qr_number") is not None:
                    user["global_qr_number"] = station.get("global_qr_number")
                if "is_dispatch" not in user and "is_dispatch" in station:
                    user["is_dispatch"] = station.get("is_dispatch")
        
        # Enrich Part Name
        part_id = user.get("part_id")
        if part_id and not user.get("part_name"):
            part = parts_collection.find_one({"part_id": part_id})
            if part:
                user["part_name"] = part.get("name")
            else:
                user["part_name"] = "N/A"
        
        # Enrich Process Step
        process_id = user.get("process_id")
        if process_id and not user.get("step"):
            from ..database import processes_collection
            proc = processes_collection.find_one({"process_id": process_id})
            if proc:
                user["step"] = proc.get("step")
        
        # Enrich Status
        if not user.get("status"):
            user["status"] = "Active"
            
        if "jobcard" not in user:
            user["jobcard"] = True
            
        return user

    @staticmethod
    def create_user(user: schemas.UserCreate, current_user: dict):
        if user.role == "Super Admin":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creation of Super Admin is not allowed.")
            
        if user.role == "Master Admin" and current_user["role"] != "Super Admin":
            raise HTTPException(status_code=403, detail="Only Super Admins can create Master Admins")
            
        if user.email and users_collection.find_one({"email": user.email}):
            raise HTTPException(status_code=400, detail="Email already registered")
            
        if user.mobile_number and users_collection.find_one({"mobile_number": user.mobile_number}):
            raise HTTPException(status_code=400, detail="Mobile number already registered")
            
        # Enforce process_id verification for Master Admins
        process_name = None
        part_name = None
        part_id = user.part_id
        is_assemble = False
        is_dispatch_admin = False
        
        if user.role == "Master Admin":
            if not user.process_id:
                raise HTTPException(status_code=400, detail="Master Admins must be assigned a process_id.")
            
        if user.process_id:
            process = processes_collection.find_one({"process_id": user.process_id})
            if not process:
                raise HTTPException(status_code=400, detail=f"Process ID '{user.process_id}' does not exist.")
            process_name = process.get("name")
            part_id = process.get("part_id")
            
        if part_id:
            valid_part = parts_collection.find_one({"part_id": part_id})
            if not valid_part:
                raise HTTPException(status_code=400, detail=f"Part ID '{part_id}' resolved from process does not exist.")
            part_name = valid_part.get("name")
            is_assemble = valid_part.get("is_assemble", False)
            is_dispatch_admin = valid_part.get("is_dispatch_admin", False)
            
        # Plant Validation
        plant_id = None
        plant_name = None
        plant_address = None

        if user.role != "Dealer":
            if user.role == "Master Admin":
                if not user.plant_id:
                    raise HTTPException(status_code=400, detail="Plant ID is required for Master Admins.")
                plant_id = user.plant_id
            else:
                if current_user.get("role") == "Super Admin":
                    if not user.plant_id:
                        raise HTTPException(status_code=400, detail="Plant ID is required when created by Super Admin.")
                    plant_id = user.plant_id
                else:
                    plant_id = current_user.get("plant_id")
                    if not plant_id:
                        raise HTTPException(status_code=400, detail="Creating Admin does not have an assigned plant.")
            plant = plants_collection.find_one({"plant_id": plant_id})
            if not plant:
                raise HTTPException(status_code=400, detail=f"Plant with ID '{plant_id}' does not exist.")
            plant_name = plant.get("plant_name")
            plant_address = plant.get("plant_address")
            
        user_dict = user.model_dump() if hasattr(user, "model_dump") else user.dict()
        user_id_prefix = "DLR" if user.role == "Dealer" else "EMP"
        user_dict["user_id"] = utils.generate_custom_id(user_id_prefix, users_collection, "user_id")
        user_dict["part_id"] = part_id
        user_dict["part_name"] = part_name
        user_dict["process_name"] = process_name
        if user.role == "Master Admin":
            user_dict["is_assemble"] = is_assemble
            user_dict["is_dispatch_admin"] = is_dispatch_admin
        user_dict["plant_id"] = plant_id
        user_dict["plant_name"] = plant_name
        user_dict["plant_address"] = plant_address
        
        if current_user["role"] == "Master Admin":
            user_dict["master_admin_id"] = current_user["user_id"]
            
        user_dict["department"] = current_user.get("department") or "PRODUCTION"
            
        if user_dict.get("assigned_station_id"):
            station = stations_collection.find_one({
                "station_id": user_dict["assigned_station_id"], 
                "active": True
            })
            if not station:
                raise HTTPException(status_code=400, detail="Assigned station not found or not active")
            
            user_dict["assigned_station_name"] = station.get("name")
            if not user_dict.get("linker_capacity") and station.get("linker_capacity"):
                user_dict["linker_capacity"] = station.get("linker_capacity")
            if not user_dict.get("global_qr_number") and station.get("global_qr_number") is not None:
                user_dict["global_qr_number"] = station.get("global_qr_number")
            if "is_dispatch" in station:
                user_dict["is_dispatch"] = station.get("is_dispatch")
            
            if station.get("part_id"):
                user_dict["part_id"] = station.get("part_id")
                valid_part = parts_collection.find_one({"part_id": station.get("part_id")})
                if valid_part:
                    user_dict["part_name"] = valid_part.get("name")
        # Generate login QR code with plain text format: mobile_number;password
        user_dict["qrcode"] = UserOperations._generate_user_login_qrcode(
            user_dict["user_id"],
            user_dict.get("mobile_number"),
            user_dict.get("password"),
            current_user,
            user_dict
        )

        user_dict["password"] = auth.get_password_hash(user_dict["password"])
        
        users_collection.insert_one(user_dict)
        return UserOperations._enrich_user(user_dict)

    @staticmethod
    def get_users(current_user: dict, role: list[str] = None, page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        
        if current_user["role"] == "Master Admin":
            allowed_roles = ["Reader", "Inspector", "Linker"]
            if role:
                for r in role:
                    if r not in allowed_roles:
                        raise HTTPException(status_code=403, detail="Master Admins cannot view users with this role.")
                query["role"] = {"$in": role}
            else:
                query["role"] = {"$in": allowed_roles}
            
            # Removed master_admin_id filter to allow viewing all sub-users
        else:
            if role:
                query["role"] = {"$in": role}

        if search:
            query["$or"] = [
                {"first_name": {"$regex": search, "$options": "i"}},
                {"last_name": {"$regex": search, "$options": "i"}},
                {"mobile_number": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"employee_id": {"$regex": search, "$options": "i"}},
                {"user_id": {"$regex": search, "$options": "i"}}
            ]

        total_count = users_collection.count_documents(query)
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1

        skip = (page - 1) * limit
        users = list(users_collection.find(query).skip(skip).limit(limit))
        enriched_users = [UserOperations._enrich_user(u) for u in users]
        return {
            "users": enriched_users,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }

    @staticmethod
    def get_user(user_id: str, current_user: dict):
        query = {"user_id": user_id}
        
        user = users_collection.find_one(query)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if current_user["role"] == "Master Admin":
            if user["role"] not in ["Reader", "Inspector", "Linker"] and user["user_id"] != current_user["user_id"]:
                 raise HTTPException(status_code=403, detail="Master Admins can only view sub-users.")
                 
        return UserOperations._enrich_user(user, include_password=True)

    @staticmethod
    def update_user(user_id: str, user_update: schemas.UserUpdate, current_user: dict):
        query = {"user_id": user_id}
        
        if current_user["role"] == "Master Admin":
            if current_user["user_id"] != user_id:
                query["master_admin_id"] = current_user["user_id"]
        elif current_user["role"] not in ["Super Admin", "B2B Admin"]:
            if current_user["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="Access denied. You can only update your own profile.")
            
        target_user = users_collection.find_one(query)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found or access denied")
            
        if target_user["role"] == "Super Admin" and current_user["role"] != "Super Admin":
            raise HTTPException(status_code=403, detail="Only Super Admins can modify Super Admins")
            
        update_data = user_update.model_dump(exclude_unset=True) if hasattr(user_update, "model_dump") else user_update.dict(exclude_unset=True)

        if "email" in update_data and update_data["email"]:
            if users_collection.find_one({"email": update_data["email"], "user_id": {"$ne": user_id}}):
                raise HTTPException(status_code=400, detail="Email already registered")
                
        if "mobile_number" in update_data and update_data["mobile_number"]:
            if users_collection.find_one({"mobile_number": update_data["mobile_number"], "user_id": {"$ne": user_id}}):
                raise HTTPException(status_code=400, detail="Mobile number already registered")

        target_role = update_data.get("role") or target_user.get("role")
        if target_role not in ["Super Admin", "Dealer", "B2B Admin"]:
            if "plant_id" in update_data and not update_data["plant_id"]:
                raise HTTPException(status_code=400, detail="Plant ID is required for Master Admins and sub-users.")
            if "plant_id" not in update_data and not target_user.get("plant_id"):
                raise HTTPException(status_code=400, detail="Plant ID is required for Master Admins and sub-users.")

        if "plant_id" in update_data:
            plant_id = update_data["plant_id"]
            if plant_id:
                plant = plants_collection.find_one({"plant_id": plant_id})
                if not plant:
                    raise HTTPException(status_code=400, detail=f"Plant with ID '{plant_id}' does not exist.")
                update_data["plant_name"] = plant.get("plant_name")
                update_data["plant_address"] = plant.get("plant_address")
            else:
                update_data["plant_name"] = None
                update_data["plant_address"] = None

        if current_user["role"] not in ["Super Admin", "Master Admin", "B2B Admin"]:
            if current_user["role"] == "Dealer":
                restricted_fields = ["role", "employee_id", "status", "order_credit_limit", "overall_credit_limit"]
            else:
                restricted_fields = ["role", "employee_id", "mobile_number", "part_id", "shift", "status", "plant_id", "order_credit_limit", "overall_credit_limit"]
            for field in restricted_fields:
                if field in update_data:
                    raise HTTPException(status_code=403, detail=f"You are not authorized to update your own '{field}'.")
        
        if "role" in update_data:
            if update_data["role"] == "Super Admin" and target_user.get("role") != "Super Admin":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change role to Super Admin.")
            if current_user["role"] == "Master Admin":
                if update_data["role"] in ["Super Admin", "Master Admin", "B2B Admin"]:
                    raise HTTPException(status_code=403, detail="Master Admins cannot promote users to Admin roles.")
            elif current_user["role"] not in ["Super Admin", "B2B Admin"]:
                 raise HTTPException(status_code=403, detail="Sub-users cannot change roles.")

        if update_data.get("role") == "Master Admin" or (update_data.get("role") is None and target_user.get("role") == "Master Admin"):
            proc_id_to_check = update_data.get("process_id") or target_user.get("process_id")
            if proc_id_to_check is None:
                raise HTTPException(status_code=400, detail="Master Admins must be assigned a process_id.")

        if "process_id" in update_data:
            if update_data["process_id"]:
                process = processes_collection.find_one({"process_id": update_data["process_id"]})
                if not process:
                    raise HTTPException(status_code=400, detail=f"Process ID '{update_data['process_id']}' does not exist.")
                update_data["process_name"] = process.get("name")
                part_id = process.get("part_id")
                
                # Fetch & map parent part_id and part_name
                update_data["part_id"] = part_id
                if part_id:
                    valid_part = parts_collection.find_one({"part_id": part_id})
                    if valid_part:
                        update_data["part_name"] = valid_part.get("name")
                        if target_role == "Master Admin":
                            update_data["is_assemble"] = valid_part.get("is_assemble", False)
                            update_data["is_dispatch_admin"] = valid_part.get("is_dispatch_admin", False)
            else:
                update_data["process_name"] = None
                update_data["part_id"] = None
                update_data["part_name"] = None
                if target_role == "Master Admin":
                    update_data["is_assemble"] = False
                    update_data["is_dispatch_admin"] = False
            
        if "password" in update_data and update_data["password"]:
            plain_password = update_data["password"]
            mobile_number = update_data.get("mobile_number", target_user.get("mobile_number"))
            qr_user_data = {**target_user, **update_data}
            update_data["qrcode"] = UserOperations._generate_user_login_qrcode(
                user_id,
                mobile_number,
                plain_password,
                current_user,
                qr_user_data
            )
            update_data["password"] = auth.get_password_hash(plain_password)
            
        if "assigned_station_id" in update_data:
            if update_data["assigned_station_id"]:
                station = stations_collection.find_one({
                    "station_id": update_data["assigned_station_id"], 
                    "active": True
                })
                if not station:
                    raise HTTPException(status_code=400, detail="Assigned station not found or not active")
                
                update_data["assigned_station_name"] = station.get("name")
                if not update_data.get("linker_capacity") and station.get("linker_capacity"):
                    update_data["linker_capacity"] = station.get("linker_capacity")
                if station.get("global_qr_number") is not None:
                    update_data["global_qr_number"] = station.get("global_qr_number")
                if "is_dispatch" in station:
                    update_data["is_dispatch"] = station.get("is_dispatch")
                
                # Also sync part_id and part_name if they exist on station
                if station.get("part_id"):
                    update_data["part_id"] = station.get("part_id")
                    valid_part = parts_collection.find_one({"part_id": station.get("part_id")})
                    if valid_part:
                        update_data["part_name"] = valid_part.get("name")
            else:
                update_data["assigned_station_id"] = None
                update_data["assigned_station_name"] = None
                update_data["is_dispatch"] = False

        if update_data:
            users_collection.update_one({"user_id": user_id}, {"$set": update_data})
            
        updated_user = users_collection.find_one({"user_id": user_id})
        return UserOperations._enrich_user(updated_user)


    @staticmethod
    def assign_station(assignment: schemas.StationAssignment, current_user: dict):
        if assignment.timestamp.tzinfo is not None:
            assignment.timestamp = assignment.timestamp.astimezone(utils.IST).replace(tzinfo=None)
            
        # Removed mandatory master_admin_id check as it's now dynamically assigned from the station

        station = stations_collection.find_one({"station_id": assignment.station_id, "active": True})
        if not station:
            raise HTTPException(status_code=400, detail="Station not found or not active")
            
        
        if current_user["role"] not in ["Reader", "Linker", "Inspector", "Master Admin"]:
             raise HTTPException(status_code=403, detail="Only Readers, Linkers, Inspectors, and Master Admins can assign stations")
        
        from ..database import scanner_processes_collection
        now = utils.get_current_time()
        scanner_processes_collection.update_many(
            {"scanner_id": current_user["user_id"], "end_time": None},
            {"$set": {"end_time": now}}
        )
            
        update_fields = {
            "assigned_station_id": assignment.station_id,
            "assigned_station_name": station.get("name"),
            "master_admin_id": station.get("master_admin_id") # Dynamically update master_admin_id from station
        }
        
        # Also sync linker_capacity and global_qr_number from station if they exist
        if station.get("linker_capacity"):
            update_fields["linker_capacity"] = station.get("linker_capacity")
        if station.get("global_qr_number") is not None:
            update_fields["global_qr_number"] = station.get("global_qr_number")
        if "is_dispatch" in station:
            update_fields["is_dispatch"] = station.get("is_dispatch")
            
        # Also sync part_id and part_name from station
        if station.get("part_id"):
            update_fields["part_id"] = station.get("part_id")
            valid_part = parts_collection.find_one({"part_id": station.get("part_id")})
            if valid_part:
                update_fields["part_name"] = valid_part.get("name")

        # Sync plant details from station to sub-user
        if station.get("plant_id"):
            update_fields["plant_id"]      = station.get("plant_id")
            update_fields["plant_name"]    = station.get("plant_name")
            update_fields["plant_address"] = station.get("plant_address")
            
        users_collection.update_one(
            {"user_id": current_user["user_id"]},
            {"$set": update_fields}
        )
        
        updated_user = users_collection.find_one({"user_id": current_user["user_id"]})
        return UserOperations._enrich_user(updated_user)

    @staticmethod
    def delete_user(user_id: str, current_user: dict):
        query = {"user_id": user_id}
        if current_user["role"] == "Master Admin":
            query["master_admin_id"] = current_user["user_id"]
            
        target_user = users_collection.find_one(query)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found or access denied")
            
        if target_user["role"] == "Super Admin" and current_user["role"] != "Super Admin":
            raise HTTPException(status_code=403, detail="Only Super Admins can delete Super Admins")
                
        users_collection.delete_one({"user_id": user_id})
        return {"detail": "User deleted successfully"}

@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_user(
    user: schemas.UserCreate, 
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return UserOperations.create_user(user, current_user)


@router.post("/assign-station", response_model=schemas.User)
def assign_station(
    assignment: schemas.StationAssignment,
    current_user: dict = Depends(auth.RoleChecker(["Reader", "Linker", "Inspector", "Master Admin"]))
):
    return UserOperations.assign_station(assignment, current_user)

@router.get("/me", response_model=schemas.User)
def get_current_user_profile(current_user: dict = Depends(auth.get_current_user)):
    return UserOperations._enrich_user(current_user, include_password=True)


@router.get("/", response_model=schemas.UserResponse)
def get_users(
    role: list[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return UserOperations.get_users(current_user, role, page=page, limit=limit, search=search)

@router.get("/{user_id}", response_model=schemas.User)
def get_user(user_id: str, current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))):
    return UserOperations.get_user(user_id, current_user)

@router.put("/{user_id}", response_model=schemas.User)
def update_user(
    user_id: str, 
    user_update: schemas.UserUpdate, 
    current_user: dict = Depends(auth.get_current_user)
):
    return UserOperations.update_user(user_id, user_update, current_user)

@router.delete("/{user_id}")
def delete_user(
    user_id: str, 
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return UserOperations.delete_user(user_id, current_user)
