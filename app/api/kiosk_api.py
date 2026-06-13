import os
import shutil
from typing import Optional, List
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Query
from .. import schemas, auth, utils
from ..database import kiosks_collection

router = APIRouter(prefix="/api/v1/kiosk", tags=["Kiosk"])

# ─── KIOSK CACHE IMPLEMENTATION ────────────────────────────────

class KioskCache:
    _cache = {} # key: device_id, token, or global_config, value: (config_data, timestamp)
    _ttl = 3600 # Cache TTL of 1 hour

    @classmethod
    def get(cls, key: str):
        if key in cls._cache:
            data, timestamp = cls._cache[key]
            now = utils.get_current_time().timestamp()
            if now - timestamp < cls._ttl:
                return data
        return None

    @classmethod
    def set(cls, key: str, data: dict):
        cls._cache[key] = (data, utils.get_current_time().timestamp())

    @classmethod
    def invalidate(cls, key: str):
        cls._cache.pop(key, None)

    @classmethod
    def clear(cls):
        cls._cache.clear()

# ─── KIOSK CORE OPERATIONS ─────────────────────────────────────

class KioskOperations:
    @staticmethod
    def get_kiosk_config(master_admin_id: Optional[str] = None):
        cache_key = f"global_config_{master_admin_id}" if master_admin_id else "global_config_default"
        # Check Global Cache First
        cached = KioskCache.get(cache_key)
        if cached:
            return cached

        # Check Database for Kiosk config
        if master_admin_id:
            kiosk_record = kiosks_collection.find_one({"master_admin_id": master_admin_id})
        else:
            kiosk_record = kiosks_collection.find_one()

        if not kiosk_record:
            config_data = {
                "status": "success",
                "data": None
            }
            KioskCache.set(cache_key, config_data)
            return config_data

        config_data = {
            "status": "success",
            "data": {
                "device_id": kiosk_record["device_id"],
                "theme": kiosk_record["theme"],
                "is_update_mandatory": kiosk_record.get("is_update_mandatory", True),
                "apk_download_url": kiosk_record["apk_download_url"],
                "admin_pin": kiosk_record.get("admin_pin")
            }
        }

        # Cache config
        KioskCache.set(cache_key, config_data)
        KioskCache.set(kiosk_record["device_id"], config_data)

        return config_data

    @staticmethod
    def verify_pin(payload: schemas.KioskVerifyPinRequest, master_admin_id: Optional[str] = None):
        if master_admin_id:
            kiosk_record = kiosks_collection.find_one({"master_admin_id": master_admin_id})
        else:
            kiosk_record = kiosks_collection.find_one()
            
        if not kiosk_record:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "status": "error",
                    "error_code": "ERR_KIOSK_NOT_FOUND",
                    "message": "Kiosk configuration not found",
                    "data": None,
                    "details": None
                }
            )

        db_pin = kiosk_record.get("admin_pin", "847592")
        if payload.pin == db_pin:
            expiry_time = (utils.get_current_time() + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return {
                "status": "success",
                "message": "PIN verified successfully",
                "data": {
                    "is_valid": True,
                    "access_granted_until": expiry_time
                }
            }
        else:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "error_code": "ERR_INVALID_PIN",
                    "message": "Invalid PIN provided",
                    "data": {
                        "is_valid": False
                    },
                    "details": {
                        "is_valid": False
                    }
                }
            )

    @staticmethod
    def create_kiosk(
        device_id: Optional[str],
        kiosk_token: Optional[str],
        admin_pin: str,
        primary_color: str,
        secondary_color: str,
        background_color: str,
        logo: Optional[UploadFile],
        splash_image: Optional[UploadFile],
        is_update_mandatory: bool,
        apk_download_url: str,
        target_master_admin_id: Optional[str],
        current_user: dict
    ):
        if current_user["role"] == "Master Admin":
            master_admin_id = current_user["user_id"]
        else:
            master_admin_id = target_master_admin_id or current_user["user_id"]

        # Enforce singleton constraint per admin - only allow one Kiosk config creation in database per admin
        if kiosks_collection.find_one({"master_admin_id": master_admin_id}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This admin already has a Kiosk configuration in the system."
            )

        resolved_device_id = device_id
        if not resolved_device_id:
            resolved_device_id = utils.generate_custom_id("KSK", kiosks_collection, "device_id")

        if kiosks_collection.find_one({"device_id": resolved_device_id}):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kiosk with device_id '{resolved_device_id}' already registered"
            )

        base_dir = os.path.join("qrcodes", "Kiosks", resolved_device_id)
        os.makedirs(base_dir, exist_ok=True)

        logo_url = "https://your-domain.com/assets/images/kiosk_logo.png"
        if logo and logo.filename:
            ext = os.path.splitext(logo.filename)[1] or ".png"
            logo_path = os.path.join(base_dir, f"logo{ext}")
            with open(logo_path, "wb") as buf:
                shutil.copyfileobj(logo.file, buf)
            logo_url = f"/qrcodes/Kiosks/{resolved_device_id}/logo{ext}?t={int(utils.get_current_time().timestamp())}"

        splash_image_url = "https://your-domain.com/assets/images/splash_bg.png"
        if splash_image and splash_image.filename:
            ext = os.path.splitext(splash_image.filename)[1] or ".png"
            splash_path = os.path.join(base_dir, f"splash{ext}")
            with open(splash_path, "wb") as buf:
                shutil.copyfileobj(splash_image.file, buf)
            splash_image_url = f"/qrcodes/Kiosks/{resolved_device_id}/splash{ext}?t={int(utils.get_current_time().timestamp())}"

        resolved_token = kiosk_token
        if not resolved_token:
            resolved_token = utils.generate_custom_id("KTK", kiosks_collection, "kiosk_token")

        kiosk_dict = {
            "device_id": resolved_device_id,
            "kiosk_token": resolved_token,
            "admin_pin": admin_pin,
            "master_admin_id": master_admin_id,
            "theme": {
                "primary_color": primary_color,
                "secondary_color": secondary_color,
                "background_color": background_color,
                "logo_url": logo_url,
                "splash_image_url": splash_image_url
            },
            "is_update_mandatory": is_update_mandatory,
            "apk_download_url": apk_download_url,
            "created_by": current_user["user_id"],
            "created_at": utils.get_current_time()
        }

        kiosks_collection.insert_one(kiosk_dict)
        # Clear the global cache configs
        KioskCache.invalidate(f"global_config_{master_admin_id}")
        KioskCache.invalidate("global_config_default")
        kiosk_dict.pop("_id", None)
        return kiosk_dict

    @staticmethod
    def get_kiosks(current_user: dict, page: int = 1, limit: int = 50, search: str = ""):
        if current_user["role"] == "Master Admin":
            query = {"master_admin_id": current_user["user_id"]}
        else:
            query = {}

        if search:
            query["$or"] = [
                {"device_id": {"$regex": search, "$options": "i"}},
                {"master_admin_id": {"$regex": search, "$options": "i"}},
                {"apk_download_url": {"$regex": search, "$options": "i"}}
            ]

        skip = (page - 1) * limit
        kiosks = list(kiosks_collection.find(query).skip(skip).limit(limit))
        for k in kiosks:
            k.pop("_id", None)
        return kiosks

    @staticmethod
    def update_kiosk(
        device_id: str,
        kiosk_token: Optional[str],
        admin_pin: Optional[str],
        primary_color: Optional[str],
        secondary_color: Optional[str],
        background_color: Optional[str],
        logo: Optional[UploadFile],
        splash_image: Optional[UploadFile],
        is_update_mandatory: Optional[bool],
        apk_download_url: Optional[str],
        current_user: dict
    ):
        kiosk = kiosks_collection.find_one({"device_id": device_id})
        if not kiosk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kiosk config not found"
            )

        if current_user["role"] == "Master Admin" and kiosk.get("master_admin_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this Kiosk configuration."
            )

        update_data = {}
        if kiosk_token is not None:
            update_data["kiosk_token"] = kiosk_token
        if admin_pin is not None:
            update_data["admin_pin"] = admin_pin
        if is_update_mandatory is not None:
            update_data["is_update_mandatory"] = is_update_mandatory
        if apk_download_url is not None:
            update_data["apk_download_url"] = apk_download_url

        theme_update = {}
        if primary_color is not None:
            theme_update["primary_color"] = primary_color
        if secondary_color is not None:
            theme_update["secondary_color"] = secondary_color
        if background_color is not None:
            theme_update["background_color"] = background_color

        base_dir = os.path.join("qrcodes", "Kiosks", device_id)
        os.makedirs(base_dir, exist_ok=True)

        if logo and logo.filename:
            ext = os.path.splitext(logo.filename)[1] or ".png"
            logo_path = os.path.join(base_dir, f"logo{ext}")
            with open(logo_path, "wb") as buf:
                shutil.copyfileobj(logo.file, buf)
            theme_update["logo_url"] = f"/qrcodes/Kiosks/{device_id}/logo{ext}?t={int(utils.get_current_time().timestamp())}"

        if splash_image and splash_image.filename:
            ext = os.path.splitext(splash_image.filename)[1] or ".png"
            splash_path = os.path.join(base_dir, f"splash{ext}")
            with open(splash_path, "wb") as buf:
                shutil.copyfileobj(splash_image.file, buf)
            theme_update["splash_image_url"] = f"/qrcodes/Kiosks/{device_id}/splash{ext}?t={int(utils.get_current_time().timestamp())}"

        if theme_update:
            existing_theme = kiosk.get("theme", {})
            for key, val in theme_update.items():
                existing_theme[key] = val
            update_data["theme"] = existing_theme

        if update_data:
            kiosks_collection.update_one({"device_id": device_id}, {"$set": update_data})
            # Invalidate caches
            KioskCache.invalidate(device_id)
            KioskCache.invalidate(f"global_config_{kiosk.get('master_admin_id')}")
            KioskCache.invalidate("global_config_default")

        updated_kiosk = kiosks_collection.find_one({"device_id": device_id})
        updated_kiosk.pop("_id", None)
        return updated_kiosk

    @staticmethod
    def delete_kiosk(device_id: str, current_user: dict):
        kiosk = kiosks_collection.find_one({"device_id": device_id})
        if not kiosk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kiosk config not found"
            )

        if current_user["role"] == "Master Admin" and kiosk.get("master_admin_id") != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not own this Kiosk configuration."
            )

        kiosks_collection.delete_one({"device_id": device_id})
        # Invalidate Cache
        KioskCache.invalidate(device_id)
        KioskCache.invalidate(f"global_config_{kiosk.get('master_admin_id')}")
        KioskCache.invalidate("global_config_default")

        return {"message": "Kiosk config removed successfully"}

# ─── KIOSK ROUTE DEFINITIONS ───────────────────────────────────

@router.get("/config", response_model=schemas.KioskConfigResponse)
def get_kiosk_config(master_admin_id: Optional[str] = None):
    return KioskOperations.get_kiosk_config(master_admin_id)

@router.post("/verify-pin", response_model=schemas.KioskVerifyPinResponse)
def verify_pin(payload: schemas.KioskVerifyPinRequest, master_admin_id: Optional[str] = None):
    return KioskOperations.verify_pin(payload, master_admin_id)

@router.post("/", response_model=dict)
def create_kiosk_config(
    admin_pin: str = Form(...),
    primary_color: str = Form(...),
    secondary_color: str = Form(...),
    background_color: str = Form(...),
    logo: Optional[UploadFile] = File(None),
    splash_image: Optional[UploadFile] = File(None),
    is_update_mandatory: bool = Form(...),
    apk_download_url: str = Form(...),
    master_admin_id: Optional[str] = Form(None),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return KioskOperations.create_kiosk(
        None, None, admin_pin, primary_color, secondary_color, background_color, 
        logo, splash_image, is_update_mandatory, apk_download_url, master_admin_id, current_user
    )

@router.get("/", response_model=List[dict])
def get_all_kiosk_configs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return KioskOperations.get_kiosks(current_user, page=page, limit=limit, search=search)

@router.put("/{device_id}", response_model=dict)
def update_kiosk_config(
    device_id: str,
    admin_pin: Optional[str] = Form(None),
    primary_color: Optional[str] = Form(None),
    secondary_color: Optional[str] = Form(None),
    background_color: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    splash_image: Optional[UploadFile] = File(None),
    is_update_mandatory: Optional[bool] = Form(None),
    apk_download_url: Optional[str] = Form(None),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return KioskOperations.update_kiosk(
        device_id, None, admin_pin, primary_color, secondary_color, background_color, 
        logo, splash_image, is_update_mandatory, apk_download_url, current_user
    )

@router.delete("/{device_id}", response_model=dict)
def delete_kiosk_config(
    device_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return KioskOperations.delete_kiosk(device_id, current_user)
