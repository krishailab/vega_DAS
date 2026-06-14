import datetime
from typing import Any, Dict, List, Optional, Union, Sequence
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette_admin import (
    BaseAdmin,
    BaseModelView,
    BaseField,
    StringField,
    IntegerField,
    BooleanField,
    DateTimeField,
    FloatField,
    TextAreaField,
    JSONField,
    TimeField,
    EnumField
)
from starlette_admin.auth import AuthProvider, AdminUser
from starlette_admin.exceptions import LoginFailed, FormValidationError
from bson import ObjectId
from pymongo.collection import Collection

from .database import (
    users_collection,
    stations_collection,
    job_cards_collection,
    parts_collection,
    shifts_collection,
    reasons_collection,
    assets_collection,
    kiosks_collection,
    products_collection,
    qr_master_collection,
    scanner_processes_collection,
    assembly_processes_collection,
    dispatch_processes_collection,
    processes_collection,
    asset_categories_collection,
    asset_subcategories_collection,
    asset_assignments_collection,
    asset_submissions_collection,
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection,
    product_variants_collection,
    plants_collection,
    dealer_signup_requests_collection,
    b2b_inward_products_collection,
    b2b_orders_collection
)
from .auth import verify_password, get_password_hash
from . import utils

class VegaAdminAuthProvider(AuthProvider):
    """Custom starlette-admin authentication provider checking roles & bcrypt hashes."""
    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response
    ) -> Response:
        user = users_collection.find_one({
            "$or": [
                {"email": username},
                {"mobile_number": username}
            ]
        })
        if not user:
            raise LoginFailed("Invalid email/mobile number or password.")
            
        role = user.get("role")
        if role not in ["Super Admin", "Master Admin", "B2B Admin"]:
            raise LoginFailed("Access denied. Admin privileges required.")
            
        hashed_password = user.get("password")
        if not verify_password(password, hashed_password):
            raise LoginFailed("Invalid email/mobile number or password.")
            
        # Store user info in session
        request.session["admin_user"] = {
            "id": user.get("user_id"),
            "name": f"{user.get('first_name')} {user.get('last_name')}",
            "role": role,
            "email": user.get("email")
        }
        return RedirectResponse(url=request.url_for("admin:index"), status_code=303)

    async def is_authenticated(self, request: Request) -> bool:
        return "admin_user" in request.session

    async def logout(self, request: Request) -> Response:
        request.session.clear()
        return RedirectResponse(url=self.get_login_route(request), status_code=303)

    async def get_admin_user(self, request: Request) -> Optional[AdminUser]:
        admin_data = request.session.get("admin_user")
        if admin_data:
            return AdminUser(
                username=admin_data["name"]
            )
        return None

class MongoDocument:
    """Wrapper class to allow accessing dictionary fields as attributes."""
    def __init__(self, data: dict, pk_attr: str = "_id"):
        self.__dict__.update(data)
        if pk_attr in data:
            setattr(self, pk_attr, str(data[pk_attr]))
        if "_id" in data:
            self._id = str(data["_id"])

class PyMongoModelView(BaseModelView):
    """Custom starlette-admin ModelView for raw pymongo backend."""
    def __init__(
        self,
        collection: Collection,
        identity: str,
        name: str,
        fields: List[BaseField],
        pk_attr: str = "_id",
        label: Optional[str] = None,
        icon: Optional[str] = None,
    ):
        self.collection = collection
        self.identity = identity
        self.name = name
        self.label = label or name
        self.icon = icon
        self.fields = fields
        self.pk_attr = pk_attr
        super().__init__()

    async def count(
        self,
        request: Request,
        where: Union[Dict[str, Any], str, None] = None,
        **kwargs: Any
    ) -> int:
        filter_dict = self._build_filter(where)
        return self.collection.count_documents(filter_dict)

    async def find_all(
        self,
        request: Request,
        skip: int = 0,
        limit: int = 100,
        where: Union[Dict[str, Any], str, None] = None,
        order_by: Optional[List[str]] = None,
        **kwargs: Any
    ) -> List[Any]:
        filter_dict = self._build_filter(where)
        cursor = self.collection.find(filter_dict).skip(skip).limit(limit)
        
        if order_by:
            sort_list = []
            for order in order_by:
                field, direction = order.split(maxsplit=1) if " " in order else (order, "asc")
                # Handle standard Starlette-Admin pk ordering mapping
                if field == self.pk_attr and self.pk_attr != "_id":
                    field = self.pk_attr
                sort_list.append((field, 1 if direction.lower() == "asc" else -1))
            cursor = cursor.sort(sort_list)
            
        return [MongoDocument(doc, self.pk_attr) for doc in cursor]

    async def find_by_pk(self, request: Request, pk: Any) -> Any:
        query_val = ObjectId(pk) if self.pk_attr == "_id" and ObjectId.is_valid(pk) else pk
        doc = self.collection.find_one({self.pk_attr: query_val})
        return MongoDocument(doc, self.pk_attr) if doc else None

    async def find_by_pks(self, request: Request, pks: List[Any]) -> Sequence[Any]:
        query_vals = [ObjectId(pk) if self.pk_attr == "_id" and ObjectId.is_valid(pk) else pk for pk in pks]
        cursor = self.collection.find({self.pk_attr: {"$in": query_vals}})
        return [MongoDocument(doc, self.pk_attr) for doc in cursor]

    async def create(self, request: Request, data: Dict[str, Any]) -> Any:
        if self.collection == users_collection and data.get("role") == "Super Admin":
            raise FormValidationError({"role": "Creation of Super Admin is not allowed."})
        cleaned_data = self._clean_data(data)
        if self.collection == users_collection:
            if not cleaned_data.get("user_id"):
                cleaned_data["user_id"] = utils.generate_custom_id("EMP", users_collection, "user_id")
            if not cleaned_data.get("password"):
                cleaned_data["password"] = get_password_hash("123")
                
            admin_session = request.session.get("admin_user")
            creator_dept = "PRODUCTION"
            if admin_session and admin_session.get("id"):
                creator = self.collection.find_one({"user_id": admin_session["id"]})
                if creator:
                    creator_dept = creator.get("department") or "PRODUCTION"
            cleaned_data["department"] = creator_dept
            
            # Plant validation for creation
            role = cleaned_data.get("role")
            if role != "Super Admin":
                if not cleaned_data.get("plant_id"):
                    raise FormValidationError({"plant_id": "Plant ID is required for Master Admins and sub-users."})
            
            plant_id = cleaned_data.get("plant_id")
            if plant_id:
                plant = plants_collection.find_one({"plant_id": plant_id})
                if not plant:
                    raise FormValidationError({"plant_id": f"Plant with ID '{plant_id}' does not exist."})
                cleaned_data["plant_name"] = plant.get("plant_name")
                cleaned_data["plant_address"] = plant.get("plant_address")
            else:
                cleaned_data["plant_id"] = None
                cleaned_data["plant_name"] = None
                cleaned_data["plant_address"] = None

        if self.collection == plants_collection:
            if not cleaned_data.get("plant_id"):
                cleaned_data["plant_id"] = utils.generate_custom_id("PLT", plants_collection, "plant_id")
            
        if self.collection == b2b_inward_products_collection:
            variant_id = cleaned_data.get("variant_id")
            if not variant_id:
                raise FormValidationError({"variant_id": "Variant ID is required."})
            
            variant = product_variants_collection.find_one({"variant_id": variant_id})
            if not variant:
                raise FormValidationError({"variant_id": f"Product Variant with ID '{variant_id}' does not exist."})
            
            existing = b2b_inward_products_collection.find_one({"variant_id": variant_id})
            if existing:
                raise FormValidationError({"variant_id": f"Product variant '{variant_id}' is already inwarded."})
                
            if not cleaned_data.get("inward_id"):
                cleaned_data["inward_id"] = utils.generate_custom_id("B2B-INW", b2b_inward_products_collection, "inward_id")
            
            cleaned_data["sku_no"] = variant.get("sku_no")
            admin_session = request.session.get("admin_user")
            cleaned_data["created_by"] = admin_session["id"] if admin_session else "Admin"
            
            now = utils.get_current_time()
            cleaned_data["created_at"] = now
            cleaned_data["updated_at"] = now

        if self.collection == parts_collection:
            if not cleaned_data.get("part_id"):
                cleaned_data["part_id"] = utils.generate_custom_id("PTR", parts_collection, "part_id")
            
            part_id = cleaned_data["part_id"]
            part_name = cleaned_data.get("name")
            
            processes_list = cleaned_data.get("processes")
            if not processes_list:
                processes_list = [part_name] if part_name else []
            elif isinstance(processes_list, str):
                import json
                try:
                    processes_list = json.loads(processes_list)
                except Exception:
                    processes_list = [processes_list]
            
            if not isinstance(processes_list, list):
                processes_list = [processes_list]
                
            processes_list = [str(p).strip() for p in processes_list if p and str(p).strip()]
            
            from .database import processes_collection
            admin_session = request.session.get("admin_user")
            created_by = admin_session["id"] if admin_session else "Admin"
            
            for idx, p_name in enumerate(processes_list):
                existing = processes_collection.find_one({"name": p_name, "part_id": part_id})
                if existing:
                    processes_collection.update_one(
                        {"process_id": existing["process_id"]},
                        {"$set": {"step": idx + 1, "part_name": part_name}}
                    )
                else:
                    process_id = utils.generate_custom_id("PRO", processes_collection, "process_id")
                    processes_collection.insert_one({
                        "process_id": process_id,
                        "name": p_name,
                        "part_id": part_id,
                        "part_name": part_name,
                        "step": idx + 1,
                        "created_by": created_by,
                        "created_at": utils.get_current_time()
                    })

        res = self.collection.insert_one(cleaned_data)
        doc = self.collection.find_one({"_id": res.inserted_id})
        return MongoDocument(doc, self.pk_attr)

    async def edit(self, request: Request, pk: Any, data: Dict[str, Any]) -> Any:
        if self.collection == users_collection and data.get("role") == "Super Admin":
            query_val = ObjectId(pk) if self.pk_attr == "_id" and ObjectId.is_valid(pk) else pk
            existing_user = self.collection.find_one({self.pk_attr: query_val})
            if existing_user and existing_user.get("role") != "Super Admin":
                raise FormValidationError({"role": "Cannot change role to Super Admin."})
        cleaned_data = self._clean_data(data)
        query_val = ObjectId(pk) if self.pk_attr == "_id" and ObjectId.is_valid(pk) else pk
        
        # Never update the primary key identifier itself
        cleaned_data.pop(self.pk_attr, None)
        cleaned_data.pop("_id", None)

        if self.collection == users_collection:
            existing_user = self.collection.find_one({self.pk_attr: query_val})
            role = cleaned_data.get("role") or existing_user.get("role")
            if role != "Super Admin":
                if not cleaned_data.get("plant_id"):
                    raise FormValidationError({"plant_id": "Plant ID is required for Master Admins and sub-users."})
            
            plant_id = cleaned_data.get("plant_id")
            if plant_id:
                plant = plants_collection.find_one({"plant_id": plant_id})
                if not plant:
                    raise FormValidationError({"plant_id": f"Plant with ID '{plant_id}' does not exist."})
                cleaned_data["plant_name"] = plant.get("plant_name")
                cleaned_data["plant_address"] = plant.get("plant_address")
            else:
                cleaned_data["plant_id"] = None
                cleaned_data["plant_name"] = None
                cleaned_data["plant_address"] = None
        
        if self.collection == b2b_inward_products_collection:
            cleaned_data["updated_at"] = utils.get_current_time()

        if self.collection == parts_collection:
            part_id = query_val
            part_name = cleaned_data.get("name")
            
            if part_name:
                from .database import processes_collection
                processes_collection.update_many({"part_id": part_id}, {"$set": {"part_name": part_name}})
                
            processes_list = cleaned_data.get("processes")
            if processes_list is not None:
                if isinstance(processes_list, str):
                    import json
                    try:
                        processes_list = json.loads(processes_list)
                    except Exception:
                        processes_list = [processes_list]
                
                if not isinstance(processes_list, list):
                    processes_list = [processes_list]
                    
                processes_list = [str(p).strip() for p in processes_list if p and str(p).strip()]
                
                from .database import processes_collection
                admin_session = request.session.get("admin_user")
                created_by = admin_session["id"] if admin_session else "Admin"
                
                for idx, p_name in enumerate(processes_list):
                    existing = processes_collection.find_one({"name": p_name, "part_id": part_id})
                    if existing:
                        processes_collection.update_one(
                            {"process_id": existing["process_id"]},
                            {"$set": {"step": idx + 1, "part_name": part_name or existing.get("part_name")}}
                        )
                    else:
                        process_id = utils.generate_custom_id("PRO", processes_collection, "process_id")
                        processes_collection.insert_one({
                            "process_id": process_id,
                            "name": p_name,
                            "part_id": part_id,
                            "part_name": part_name or self.collection.find_one({self.pk_attr: query_val}).get("name"),
                            "step": idx + 1,
                            "created_by": created_by,
                            "created_at": utils.get_current_time()
                        })
            
        self.collection.update_one({self.pk_attr: query_val}, {"$set": cleaned_data})
        doc = self.collection.find_one({self.pk_attr: query_val})
        return MongoDocument(doc, self.pk_attr)

    async def delete(self, request: Request, pks: List[Any]) -> None:
        query_vals = [ObjectId(pk) if self.pk_attr == "_id" and ObjectId.is_valid(pk) else pk for pk in pks]
        self.collection.delete_many({self.pk_attr: {"$in": query_vals}})

    def _build_filter(self, where: Union[Dict[str, Any], str, None]) -> Dict[str, Any]:
        if not where:
            return {}
        if isinstance(where, str):
            # global text search: filter matching regex on all StringFields
            search_filters = []
            for field in self.fields:
                if isinstance(field, StringField):
                    search_filters.append({field.name: {"$regex": where, "$options": "i"}})
            if search_filters:
                return {"$or": search_filters}
            return {}
        
        # Simple dict filter mapping
        filter_dict = {}
        for k, v in where.items():
            # If value is dictionary and contains starlette-admin complex search terms, we map it
            # For simplicity, map direct matching
            filter_dict[k] = v
        return filter_dict

    def _clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = {}
        for k, v in data.items():
            if k == "_id":
                continue
            # Convert empty values or format them if needed
            cleaned[k] = v
        return cleaned

# --- Admin Dashboard Definition ---

admin = BaseAdmin(
    title="Vega Track Admin Dashboard",
    base_url="/admin",
    route_name="admin",
    auth_provider=VegaAdminAuthProvider()
)

# --- Register Views ---

# 1. Users View
admin.add_view(
    PyMongoModelView(
        collection=users_collection,
        identity="users",
        name="User",
        label="Users",
        icon="fa fa-users",
        pk_attr="user_id",
        fields=[
            StringField("user_id", label="User ID", read_only=True),
            StringField("first_name", label="First Name", required=True),
            StringField("last_name", label="Last Name", required=True),
            StringField("email", label="Email", required=True),
            StringField("mobile_number", label="Mobile Number"),
            StringField("role", label="Role", required=True),
            StringField("employee_id", label="Employee ID"),
            StringField("shift", label="Shift"),
            IntegerField("age", label="Age"),
            StringField("gender", label="Gender"),
            StringField("blood_group", label="Blood Group"),
            StringField("status", label="Status"),
            BooleanField("is_dispatch", label="Is Dispatch"),
            IntegerField("linker_capacity", label="Linker Capacity"),
            StringField("assigned_station_id", label="Assigned Station ID"),
            StringField("department", label="Department"),
            StringField("plant_id", label="Plant ID"),
            StringField("plant_name", label="Plant Name", read_only=True),
            StringField("plant_address", label="Plant Address", read_only=True),
        ]
    )
)

# 2. Stations View
admin.add_view(
    PyMongoModelView(
        collection=stations_collection,
        identity="stations",
        name="Station",
        label="Stations",
        icon="fa fa-building",
        pk_attr="station_id",
        fields=[
            StringField("station_id", label="Station ID", read_only=True),
            StringField("name", label="Station Name", required=True),
            StringField("process", label="Process Name"),
            BooleanField("active", label="Active", required=True),
            StringField("comment", label="Comment"),
            IntegerField("linker_capacity", label="Linker Capacity"),
            IntegerField("global_qr_number", label="Global QR Number"),
            StringField("part_id", label="Part ID"),
            StringField("master_admin_id", label="Master Admin ID"),
            BooleanField("is_dispatch", label="Is Dispatch"),
            StringField("qrcode", label="QR Code Path"),
            StringField("plant_id", label="Plant ID"),
            StringField("plant_name", label="Plant Name", read_only=True),
            StringField("plant_address", label="Plant Address", read_only=True),
        ]
    )
)

# 3. Job Cards View
admin.add_view(
    PyMongoModelView(
        collection=job_cards_collection,
        identity="job_cards",
        name="Job Card",
        label="Job Cards",
        icon="fa fa-id-card",
        pk_attr="jobcard_id",
        fields=[
            StringField("jobcard_id", label="Job Card ID", read_only=True),
            StringField("jobcard_no", label="Job Card No", required=True),
            StringField("jobcard_date", label="Date", required=True),
            StringField("part_composition", label="Part Composition"),
            IntegerField("quantity", label="Quantity", required=True),
            StringField("part_id", label="Part ID"),
            StringField("part_model", label="Part Model"),
            StringField("status", label="Status"),
            EnumField("currency", label="Currency", choices=["INR", "USD", "CAD"]),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 4. Parts View
admin.add_view(
    PyMongoModelView(
        collection=parts_collection,
        identity="parts",
        name="Part",
        label="Parts",
        icon="fa fa-cogs",
        pk_attr="part_id",
        fields=[
            StringField("part_id", label="Part ID", read_only=True),
            StringField("name", label="Part Name", required=True),
            StringField("type", label="Type", required=True),
            BooleanField("active", label="Active", required=True),
            BooleanField("is_assemble", label="Is Assemble"),
            BooleanField("is_dispatch_admin", label="Is Dispatch Admin"),
            JSONField("processes", label="Processes (JSON Array of Names)"),
        ]
    )
)

# 5. Shifts View
admin.add_view(
    PyMongoModelView(
        collection=shifts_collection,
        identity="shifts",
        name="Shift",
        label="Shifts",
        icon="fa fa-clock",
        pk_attr="shift_id",
        fields=[
            StringField("shift_id", label="Shift ID", read_only=True),
            StringField("name", label="Shift Name", required=True),
            StringField("start_time", label="Start Time"),
            StringField("end_time", label="End Time"),
            BooleanField("active", label="Active", required=True),
        ]
    )
)

# 6. Reasons View
admin.add_view(
    PyMongoModelView(
        collection=reasons_collection,
        identity="reasons",
        name="Reason",
        label="Reasons",
        icon="fa fa-exclamation-triangle",
        pk_attr="reason_id",
        fields=[
            StringField("reason_id", label="Reason ID", read_only=True),
            StringField("name", label="Reason Description", required=True),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 7. Assets View
admin.add_view(
    PyMongoModelView(
        collection=assets_collection,
        identity="assets",
        name="Asset",
        label="Assets",
        icon="fa fa-laptop",
        pk_attr="asset_id",
        fields=[
            StringField("asset_id", label="Asset ID", read_only=True),
            StringField("name", label="Asset Name", required=True),
            StringField("asset_no", label="Asset No", required=True),
            StringField("model", label="Model"),
            StringField("brand", label="Brand"),
            StringField("purchase_date", label="Purchase Date"),
            FloatField("cost", label="Cost"),
            StringField("status", label="Status"),
            StringField("category_id", label="Category ID"),
            StringField("subcategory_id", label="Subcategory ID"),
            BooleanField("is_warranty", label="Is Warranty"),
            BooleanField("is_guarantee", label="Is Guarantee"),
            StringField("warranty_expiry_date", label="Warranty Expiry Date"),
            StringField("maintenance_period", label="Maintenance Period"),
            StringField("comment", label="Comment"),
        ]
    )
)

# 8. Kiosks View
admin.add_view(
    PyMongoModelView(
        collection=kiosks_collection,
        identity="kiosks",
        name="Kiosk",
        label="Kiosks",
        icon="fa fa-desktop",
        pk_attr="device_id",
        fields=[
            StringField("device_id", label="Device ID", required=True),
            StringField("admin_pin", label="Admin PIN", required=True),
            JSONField("theme", label="Theme Configuration"),
            BooleanField("is_update_mandatory", label="Mandatory Update"),
            StringField("apk_download_url", label="APK Download URL"),
        ]
    )
)

# 9. Products View
admin.add_view(
    PyMongoModelView(
        collection=products_collection,
        identity="products",
        name="Product",
        label="Products",
        icon="fa fa-box",
        pk_attr="product_id",
        fields=[
            StringField("product_id", label="Product ID", read_only=True),
            StringField("name", label="Product Name", required=True),
            StringField("sku_no", label="SKU Number"),
            BooleanField("active", label="Active", required=True),
        ]
    )
)

# 10. QR Master View
admin.add_view(
    PyMongoModelView(
        collection=qr_master_collection,
        identity="qr_master",
        name="QR Master",
        label="QR Master",
        icon="fa fa-qrcode",
        pk_attr="qr_id",
        fields=[
            StringField("qr_id", label="QR ID", read_only=True),
            StringField("jobcard_id", label="Job Card ID"),
            StringField("part_id", label="Part ID"),
            StringField("master_admin_id", label="Master Admin ID"),
            StringField("status", label="Status"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 11. Scanner Processes View
admin.add_view(
    PyMongoModelView(
        collection=scanner_processes_collection,
        identity="scanner_processes",
        name="Scanner Process",
        label="Scanner Processes",
        icon="fa fa-barcode",
        pk_attr="scan_id",
        fields=[
            StringField("scan_id", label="Scan ID", read_only=True),
            StringField("qr_id", label="QR ID", required=True),
            StringField("station_id", label="Station ID"),
            StringField("station_name", label="Station Name"),
            StringField("scanner_id", label="Scanner ID"),
            StringField("scanner_name", label="Scanner Name"),
            StringField("inspection_status", label="Inspection Status"),
            DateTimeField("start_time", label="Start Time"),
            DateTimeField("end_time", label="End Time"),
            StringField("inspector_id", label="Inspector ID"),
            StringField("inspector_name", label="Inspector Name"),
            StringField("reject_reason", label="Reject Reason"),
            StringField("rejection_image", label="Rejection Image"),
            BooleanField("is_latest", label="Is Latest"),
        ]
    )
)

# 12. Assembly Processes View
admin.add_view(
    PyMongoModelView(
        collection=assembly_processes_collection,
        identity="assembly_processes",
        name="Assembly Process",
        label="Assembly Processes",
        icon="fa fa-tools",
        pk_attr="assembly_id",
        fields=[
            StringField("assembly_id", label="Assembly ID", read_only=True),
            JSONField("qr_ids", label="QR IDs"),
            JSONField("component_ids", label="Component IDs"),
            StringField("process_name", label="Process Name"),
            StringField("station_id", label="Station ID"),
            StringField("linker_id", label="Linker ID"),
            StringField("inspection_status", label="Inspection Status"),
            DateTimeField("start_time", label="Start Time"),
            DateTimeField("end_time", label="End Time"),
            StringField("inspector_id", label="Inspector ID"),
            StringField("station_name", label="Station Name"),
            StringField("linker_name", label="Linker Name"),
            StringField("inspector_name", label="Inspector Name"),
            StringField("reject_reason", label="Reject Reason"),
            BooleanField("is_latest", label="Is Latest"),
        ]
    )
)

# 13. Dispatch Processes View
admin.add_view(
    PyMongoModelView(
        collection=dispatch_processes_collection,
        identity="dispatch_processes",
        name="Dispatch Process",
        label="Dispatch Processes",
        icon="fa fa-truck",
        pk_attr="dispatch_id",
        fields=[
            StringField("dispatch_id", label="Dispatch ID", read_only=True),
            JSONField("qr_ids", label="QR IDs"),
            JSONField("component_ids", label="Component IDs"),
            StringField("process_name", label="Process Name"),
            StringField("station_id", label="Station ID"),
            StringField("linker_id", label="Linker ID"),
            StringField("inspection_status", label="Inspection Status"),
            DateTimeField("start_time", label="Start Time"),
            DateTimeField("end_time", label="End Time"),
            StringField("inspector_id", label="Inspector ID"),
            StringField("station_name", label="Station Name"),
            StringField("linker_name", label="Linker Name"),
            StringField("inspector_name", label="Inspector Name"),
            StringField("reject_reason", label="Reject Reason"),
            BooleanField("is_latest", label="Is Latest"),
        ]
    )
)

# 14. Processes View
admin.add_view(
    PyMongoModelView(
        collection=processes_collection,
        identity="processes",
        name="Process",
        label="Processes",
        icon="fa fa-tasks",
        pk_attr="process_id",
        fields=[
            StringField("process_id", label="Process ID", read_only=True),
            StringField("name", label="Process Name", required=True),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 15. Asset Categories View
admin.add_view(
    PyMongoModelView(
        collection=asset_categories_collection,
        identity="asset_categories",
        name="Asset Category",
        label="Asset Categories",
        icon="fa fa-tags",
        pk_attr="category_id",
        fields=[
            StringField("category_id", label="Category ID", read_only=True),
            StringField("name", label="Category Name", required=True),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 16. Asset Subcategories View
admin.add_view(
    PyMongoModelView(
        collection=asset_subcategories_collection,
        identity="asset_subcategories",
        name="Asset Subcategory",
        label="Asset Subcategories",
        icon="fa fa-tag",
        pk_attr="subcategory_id",
        fields=[
            StringField("subcategory_id", label="Subcategory ID", read_only=True),
            StringField("category_id", label="Category ID", required=True),
            StringField("category_name", label="Category Name"),
            StringField("name", label="Subcategory Name", required=True),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 17. Asset Assignments View
admin.add_view(
    PyMongoModelView(
        collection=asset_assignments_collection,
        identity="asset_assignments",
        name="Asset Assignment",
        label="Asset Assignments",
        icon="fa fa-clipboard-list",
        pk_attr="assignment_id",
        fields=[
            StringField("assignment_id", label="Assignment ID", read_only=True),
            StringField("asset_id", label="Asset ID", required=True),
            StringField("asset_name", label="Asset Name"),
            StringField("user_id", label="User ID", required=True),
            StringField("user_name", label="User Name"),
            StringField("role", label="User Role"),
            StringField("assigned_by", label="Assigned By"),
            StringField("assigned_by_name", label="Assigned By Name"),
            DateTimeField("assigned_at", label="Assigned At"),
            TextAreaField("notes", label="Notes"),
            BooleanField("is_active", label="Is Active"),
        ]
    )
)

# 18. Asset Submissions View
admin.add_view(
    PyMongoModelView(
        collection=asset_submissions_collection,
        identity="asset_submissions",
        name="Asset Submission",
        label="Asset Submissions",
        icon="fa fa-hand-holding",
        pk_attr="submission_id",
        fields=[
            StringField("submission_id", label="Submission ID", read_only=True),
            StringField("asset_id", label="Asset ID", required=True),
            StringField("asset_name", label="Asset Name"),
            StringField("assignment_id", label="Assignment ID", required=True),
            StringField("assigned_user_id", label="Assigned User ID"),
            StringField("assigned_user_name", label="Assigned User Name"),
            StringField("status", label="Status", required=True),
            StringField("condition", label="Condition"),
            TextAreaField("remarks", label="Remarks"),
            StringField("submitted_by", label="Submitted By"),
            StringField("submitted_by_name", label="Submitted By Name"),
            DateTimeField("submitted_at", label="Submitted At"),
        ]
    )
)

# 19. Product Categories View
admin.add_view(
    PyMongoModelView(
        collection=product_categories_collection,
        identity="product_categories",
        name="Product Category",
        label="Product Categories",
        icon="fa fa-folder",
        pk_attr="category_id",
        fields=[
            StringField("category_id", label="Category ID", read_only=True),
            StringField("name", label="Category Name", required=True),
            BooleanField("is_active", label="Is Active"),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 20. Product Subcategories View
admin.add_view(
    PyMongoModelView(
        collection=product_subcategories_collection,
        identity="product_subcategories",
        name="Product Subcategory",
        label="Product Subcategories",
        icon="fa fa-folder-open",
        pk_attr="subcategory_id",
        fields=[
            StringField("subcategory_id", label="Subcategory ID", read_only=True),
            StringField("category_id", label="Category ID", required=True),
            StringField("name", label="Subcategory Name", required=True),
            BooleanField("is_active", label="Is Active"),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 21. Product Brands View
admin.add_view(
    PyMongoModelView(
        collection=product_brands_collection,
        identity="product_brands",
        name="Product Brand",
        label="Product Brands",
        icon="fa fa-copyright",
        pk_attr="brand_id",
        fields=[
            StringField("brand_id", label="Brand ID", read_only=True),
            StringField("name", label="Brand Name", required=True),
            TextAreaField("description", label="Description"),
            BooleanField("is_active", label="Is Active"),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 22. Product Models View
admin.add_view(
    PyMongoModelView(
        collection=product_models_collection,
        identity="product_models",
        name="Product Model",
        label="Product Models",
        icon="fa fa-cubes",
        pk_attr="model_id",
        fields=[
            StringField("model_id", label="Model ID", read_only=True),
            StringField("name", label="Model Name", required=True),
            StringField("brand_id", label="Brand ID", required=True),
            StringField("category_id", label="Category ID", required=True),
            StringField("subcategory_id", label="Subcategory ID", required=True),
            BooleanField("is_active", label="Is Active"),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 23. Product Submodels View
admin.add_view(
    PyMongoModelView(
        collection=product_submodels_collection,
        identity="product_submodels",
        name="Product Submodel",
        label="Product Submodels",
        icon="fa fa-cube",
        pk_attr="submodel_id",
        fields=[
            StringField("submodel_id", label="Submodel ID", read_only=True),
            StringField("name", label="Submodel Name", required=True),
            StringField("model_id", label="Model ID", required=True),
            StringField("image", label="Submodel Image"),
            BooleanField("is_active", label="Is Active"),
            FloatField("box_weight", label="Box Weight"),
            StringField("box_dimension", label="Box Dimension"),
            FloatField("carton_weight", label="Carton Weight"),
            StringField("carton_dimension", label="Carton Dimension"),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 24. Product Variants View
admin.add_view(
    PyMongoModelView(
        collection=product_variants_collection,
        identity="product_variants",
        name="Product Variant",
        label="Product Variants",
        icon="fa fa-sliders-h",
        pk_attr="variant_id",
        fields=[
            StringField("variant_id", label="Variant ID", read_only=True),
            StringField("sku_no", label="SKU No", required=True),
            StringField("submodel_id", label="Submodel ID", required=True),
            StringField("gs1_barcode", label="GS1 Barcode"),
            TextAreaField("short_description", label="Short Description"),
            TextAreaField("long_description", label="Long Description"),
            IntegerField("carton_box_size", label="Carton Box Size"),
            StringField("carton_barcode", label="Carton Barcode"),
            JSONField("product_images", label="Product Images"),
            StringField("color", label="Color"),
            StringField("size_name", label="Size Name"),
            IntegerField("size", label="Size"),
            StringField("finish", label="Finish"),
            JSONField("certification", label="Certification"),
            StringField("visor_type", label="Visor Type"),
            StringField("spoiler", label="Spoiler"),
            StringField("chinstrap_lock", label="Chinstrap Lock"),
            StringField("pinlock", label="Pinlock"),
            JSONField("mrp", label="MRP (Dynamic Currency Map)"),
            BooleanField("is_active", label="Is Active"),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At"),
        ]
    )
)

# 25. Plants View
admin.add_view(
    PyMongoModelView(
        collection=plants_collection,
        identity="plants",
        name="Plant",
        label="Plants",
        icon="fa fa-industry",
        pk_attr="plant_id",
        fields=[
            StringField("plant_id", label="Plant ID", read_only=True),
            StringField("plant_name", label="Plant Name", required=True),
            StringField("plant_address", label="Plant Address", required=True),
            StringField("status", label="Status"),
        ]
    )
)

admin.add_view(
    PyMongoModelView(
        collection=dealer_signup_requests_collection,
        identity="dealer_signup_requests",
        name="Dealer Signup Request",
        label="Dealer Signups",
        icon="fa fa-user-plus",
        pk_attr="request_id",
        fields=[
            StringField("request_id", label="Request ID", read_only=True),
            StringField("business_name", label="Business Name", required=True),
            StringField("contact_name", label="Contact Person", required=True),
            StringField("email", label="Email Address", required=True),
            StringField("mobile_number", label="Mobile Number", required=True),
            StringField("alternate_mobile_number", label="Alternate Mobile"),
            TextAreaField("address", label="Address", required=True),
            StringField("city", label="City", required=True),
            StringField("state", label="State", required=True),
            StringField("pincode", label="Pincode", required=True),
            TextAreaField("comments", label="Comments"),
            StringField("status", label="Status"),
            StringField("processed_by", label="Processed By ID", read_only=True),
            StringField("reject_reason", label="Reject Reason"),
            DateTimeField("created_at", label="Created At", read_only=True),
            DateTimeField("updated_at", label="Updated At", read_only=True),
        ]
    )
)
admin.add_view(
    PyMongoModelView(
        collection=b2b_inward_products_collection,
        identity="b2b_inward_products",
        name="B2B Inward Product",
        label="B2B Inwards",
        icon="fa fa-boxes",
        pk_attr="inward_id",
        fields=[
            StringField("inward_id", label="Inward ID", read_only=True),
            StringField("variant_id", label="Variant ID", required=True),
            StringField("sku_no", label="SKU No", read_only=True),
            FloatField("dealer_price", label="Dealer Price", required=True),
            EnumField("currency", label="Currency", choices=["INR", "USD", "CAD"]),
            BooleanField("is_individual", label="Is Individual"),
            BooleanField("is_carton", label="Is Carton"),
            BooleanField("is_featured", label="Is Featured"),
            BooleanField("is_new_arrival", label="Is New Arrival"),
            BooleanField("is_best_seller", label="Is Best Seller"),
            BooleanField("is_active", label="Is Active"),
            StringField("created_by", label="Created By"),
            DateTimeField("created_at", label="Created At", read_only=True),
            DateTimeField("updated_at", label="Updated At", read_only=True),
        ]
    )
)
admin.add_view(
    PyMongoModelView(
        collection=b2b_orders_collection,
        identity="b2b_orders",
        name="B2B Order",
        label="B2B Orders",
        icon="fa fa-shopping-bag",
        pk_attr="order_id",
        fields=[
            StringField("order_id", label="Order ID", read_only=True),
            StringField("user_id", label="Dealer User ID", required=True),
            JSONField("company_address", label="Company Address"),
            JSONField("items", label="Order Items"),
            IntegerField("total_items", label="Total Items"),
            FloatField("total_price", label="Total Price"),
            StringField("status", label="Status"),
            DateTimeField("created_at", label="Created At", read_only=True),
            DateTimeField("updated_at", label="Updated At", read_only=True),
        ]
    )
)



