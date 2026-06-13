from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid
from .. import schemas, auth, utils
from ..database import stations_collection
from fastapi.responses import StreamingResponse
import io
import os
from PIL import Image, ImageDraw, ImageFont

router = APIRouter(prefix="/stations", tags=["Stations"])

class StationOperations:
    @staticmethod
    def create_station(station: schemas.StationCreate, current_user: dict):
        if stations_collection.find_one({"name": station.name, "master_admin_id": current_user["user_id"]}):
            raise HTTPException(status_code=400, detail="Station already registered for this Master Admin")
        
        station_dict = station.model_dump() if hasattr(station, "model_dump") else station.dict()
        
        # Automatically assign part_id from Master Admin profile
        part_id = current_user.get("part_id")
        if not part_id:
            raise HTTPException(status_code=400, detail="Master Admin has no part assigned in profile.")
            
        station_dict["part_id"] = part_id

        from ..database import parts_collection, plants_collection
        part = parts_collection.find_one({"part_id": part_id})
        if not part:
            raise HTTPException(status_code=400, detail="Assigned Part ID not found in database")

        # Validate plant if explicitly provided in the payload, else inherit from the creating user
        if station_dict.get("plant_id"):
            plant = plants_collection.find_one({"plant_id": station_dict["plant_id"]})
            if not plant:
                raise HTTPException(status_code=400, detail=f"Plant ID '{station_dict['plant_id']}' does not exist.")
            station_dict["plant_name"]    = plant.get("plant_name")
            station_dict["plant_address"] = plant.get("plant_address")
        else:
            # Fall back to the Master Admin's own plant assignment
            station_dict["plant_id"]      = current_user.get("plant_id")
            station_dict["plant_name"]    = current_user.get("plant_name")
            station_dict["plant_address"] = current_user.get("plant_address")

        # Automatically assign process and process_id from Master Admin profile
        station_dict["process_id"] = current_user.get("process_id")
        station_dict["process"] = current_user.get("process_name") or current_user.get("process")

        station_dict["station_id"]   = utils.generate_custom_id("STN", stations_collection, "station_id")
        station_dict["master_admin_id"] = current_user["user_id"]
        station_dict["qrcode"] = utils.generate_qr_file(station_dict["station_id"], current_user["user_id"], "Station", station_dict["station_id"])
        
        stations_collection.insert_one(station_dict)
        station_dict.pop("_id", None)
        return station_dict


    @staticmethod
    def get_stations(current_user: dict, page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if current_user.get("role") != "Super Admin":
            plant_id = current_user.get("plant_id")
            process_id = current_user.get("process_id")
            if plant_id and process_id:
                query = {
                    "$or": [
                        {"master_admin_id": current_user["user_id"]},
                        {"plant_id": plant_id, "process_id": process_id}
                    ]
                }
            else:
                query["master_admin_id"] = current_user["user_id"]
            
        if search:
            search_filter = [
                {"name": {"$regex": search, "$options": "i"}},
                {"station_id": {"$regex": search, "$options": "i"}},
                {"process": {"$regex": search, "$options": "i"}},
                {"plant_name": {"$regex": search, "$options": "i"}}
            ]
            if "$or" in query:
                query = {"$and": [query, {"$or": search_filter}]}
            else:
                query["$or"] = search_filter

        skip = (page - 1) * limit
        stations = list(stations_collection.find(query).skip(skip).limit(limit))
        for s in stations:
            s.pop("_id", None)
        return stations

    @staticmethod
    def update_station(station_id: str, station: schemas.StationUpdate, current_user: dict):
        plant_id = current_user.get("plant_id")
        process_id = current_user.get("process_id")
        query = {"station_id": station_id}
        if current_user.get("role") != "Super Admin":
            if plant_id and process_id:
                query["$or"] = [
                    {"master_admin_id": current_user["user_id"]},
                    {"plant_id": plant_id, "process_id": process_id}
                ]
            else:
                query["master_admin_id"] = current_user["user_id"]
                
        existing = stations_collection.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Station not found")
            
        update_data = station.model_dump(exclude_unset=True) if hasattr(station, "model_dump") else station.dict(exclude_unset=True)
        
        # Validate global_qr_number vs linker_capacity
        new_qr = update_data.get("global_qr_number", existing.get("global_qr_number"))
        new_cap = update_data.get("linker_capacity", existing.get("linker_capacity"))
        if new_qr is not None and new_cap is not None:
            if new_qr > new_cap:
                raise HTTPException(status_code=400, detail="global_qr_number cannot be greater than linker_capacity")

        # Validate part_id
        if "part_id" in update_data:
            if update_data["part_id"] is None:
                raise HTTPException(status_code=400, detail="part_id cannot be null")
                
            from ..database import parts_collection
            part = parts_collection.find_one({"part_id": update_data["part_id"]})
            if not part:
                raise HTTPException(status_code=400, detail="Part ID not found")

        # Automatic update of process_id if process or part_id changes
        if "process" in update_data or "part_id" in update_data:
            p_name = update_data.get("process", existing.get("process"))
            part_id = update_data.get("part_id", existing.get("part_id"))
            if p_name and part_id:
                from ..database import processes_collection
                proc = processes_collection.find_one({"name": p_name.strip(), "part_id": part_id})
                if proc:
                    update_data["process_id"] = proc.get("process_id")
                else:
                    update_data["process_id"] = None
            else:
                update_data["process_id"] = None

        if update_data:
            stations_collection.update_one({"station_id": station_id}, {"$set": update_data})
        
        updated = stations_collection.find_one({"station_id": station_id})
        updated.pop("_id", None)
        return updated



    @staticmethod
    def download_station_qr_pdf(station_id: str, current_user: dict):
        plant_id = current_user.get("plant_id")
        process_id = current_user.get("process_id")
        query = {"station_id": station_id}
        if current_user.get("role") != "Super Admin":
            if plant_id and process_id:
                query["$or"] = [
                    {"master_admin_id": current_user["user_id"]},
                    {"plant_id": plant_id, "process_id": process_id}
                ]
            else:
                query["master_admin_id"] = current_user["user_id"]
                
        station = stations_collection.find_one(query)
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
            
        qr_path = station.get("qrcode")
        if not qr_path or not os.path.exists(qr_path):
            qr_path = utils.generate_qr_file(station_id, current_user["user_id"], "Station", station_id)
            stations_collection.update_one({"station_id": station_id}, {"$set": {"qrcode": qr_path}})

        img = Image.open(qr_path).convert("RGB")

        width, height = 800, 1250
        canvas = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(canvas)

        # --- Fonts (cross-platform: tries system fonts, falls back to Pillow default) ---
        def _load_font(bold=False, size=24):
            candidates = [
                # Linux (DejaVu — ships with most distros)
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"          if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                # Linux (Liberation)
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                # macOS
                "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
            for path in candidates:
                if os.path.exists(path):
                    try:
                        return ImageFont.truetype(path, size)
                    except Exception:
                        continue
            # Pillow >= 10 supports size param on load_default
            try:
                return ImageFont.load_default(size=size)
            except TypeError:
                return ImageFont.load_default()

        font_regular = _load_font(bold=False, size=24)
        font_info    = _load_font(bold=True,  size=24)
        font_small   = _load_font(bold=False, size=16)

        app_dir = os.path.dirname(os.path.abspath(__file__))
        assets  = os.path.join(app_dir, "..")

        # --- Top-left: Vega Central logo ---
        try:
            vc_logo = Image.open(os.path.join(assets, "vegacentral.png"))
            vc_logo = vc_logo.resize((120, 120), Image.Resampling.LANCZOS)
            canvas.paste(vc_logo, (50, 50), vc_logo if vc_logo.mode == "RGBA" else None)
        except Exception:
            pass

        # --- Top-right: Vega + Axor logos + URL ---
        try:
            vega_logo = Image.open(os.path.join(assets, "vega.png")).resize((100, 40), Image.Resampling.LANCZOS)
            axor_logo = Image.open(os.path.join(assets, "axor.png")).resize((100, 40), Image.Resampling.LANCZOS)
            canvas.paste(vega_logo, (550, 60), vega_logo if vega_logo.mode == "RGBA" else None)
            canvas.paste(axor_logo, (660, 60), axor_logo if axor_logo.mode == "RGBA" else None)
            draw.text((655, 110), "central.vegaauto.in", fill="black", font=font_small, anchor="mm")
        except Exception:
            pass

        # --- QR Code (centered) ---
        qr_display_size = 650
        qr_x = (width - qr_display_size) // 2
        qr_y = 180
        img = img.resize((qr_display_size, qr_display_size), Image.Resampling.LANCZOS)
        canvas.paste(img, (qr_x, qr_y))

        # --- Details box ---
        box_y      = qr_y + qr_display_size + 40
        box_width  = 700
        box_height = 180
        box_x      = (width - box_width) // 2
        draw.rectangle([box_x, box_y, box_x + box_width, box_y + box_height], outline="black", width=2)
        tp = 20
        draw.text((box_x + tp, box_y + 20),  f"Machine Code: {station.get('name', 'N/A')}", fill="black", font=font_info)
        draw.text((box_x + tp, box_y + 65),  f"Process: {station.get('process', 'N/A')}",   fill="black", font=font_info)
        draw.text((box_x + tp, box_y + 110), f"QR ID: {station_id}",                         fill="black", font=font_info)

        # --- Footer: Motocross logo left, credit text to its right (no overlap) ---
        try:
            footer_logo = Image.open(os.path.join(assets, "motocross.png"))
            footer_h = 50
            orig_w, orig_h = footer_logo.size
            footer_w = int(orig_w * footer_h / orig_h)
            footer_logo = footer_logo.resize((footer_w, footer_h), Image.Resampling.LANCZOS)

            footer_strip_top = height - 100
            logo_x = 100
            logo_y = footer_strip_top + (100 - footer_h) // 2

            if footer_logo.mode == "RGBA":
                canvas.paste(footer_logo, (logo_x, logo_y), footer_logo)
            else:
                canvas.paste(footer_logo, (logo_x, logo_y))

            text_x = logo_x + footer_w + 15
            text_y = footer_strip_top + 50
            draw.text((text_x, text_y), "Designed & developed by NxtLab | www.nxtlab.in",
                      fill="#444444", font=font_small, anchor="lm")
        except Exception:
            pass

        buf = io.BytesIO()
        canvas.save(buf, format="PDF")
        buf.seek(0)

        headers = {"Content-Disposition": f'attachment; filename="station_{station_id}.pdf"'}
        return StreamingResponse(buf, media_type="application/pdf", headers=headers)

@router.post("/", response_model=schemas.Station, status_code=status.HTTP_201_CREATED)
def create_station(
    station: schemas.StationCreate, 
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return StationOperations.create_station(station, current_user)

@router.get("/", response_model=list[schemas.Station])
def get_stations(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin"]))
):
    return StationOperations.get_stations(current_user, page=page, limit=limit, search=search)

@router.put("/{station_id}", response_model=schemas.Station)
def update_station(
    station_id: str,
    station: schemas.StationUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin"]))
):
    return StationOperations.update_station(station_id, station, current_user)



@router.get("/{station_id}/download-pdf")
def download_station_qr_pdf(
    station_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Master Admin", "Super Admin"]))
):
    return StationOperations.download_station_qr_pdf(station_id, current_user)
