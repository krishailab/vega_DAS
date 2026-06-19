import create_initial_jobcards
from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Optional, Union, Any
from datetime import datetime, time

class UserBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    employee_id: Optional[str] = None
    mobile_number: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    shift: Optional[str] = None
    part_id: Optional[str] = None
    status: str = "Active"
    assigned_station_id: Optional[str] = None
    linker_capacity: Optional[int] = None
    is_dispatch: Optional[bool] = False
    is_assemble: Optional[bool] = False
    is_dispatch_admin: Optional[bool] = False
    department: Optional[str] = None
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None
    business_name: Optional[str] = None
    alternate_mobile_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    process_id: Optional[str] = None
    process_name: Optional[str] = None
    order_credit_limit: Optional[float] = None
    overall_credit_limit: Optional[float] = None
    jobcard: bool = True


class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    employee_id: Optional[str] = None
    mobile_number: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    shift: Optional[str] = None
    password: Optional[str] = None
    part_id: Optional[str] = None
    process_id: Optional[str] = None
    process_name: Optional[str] = None
    status: Optional[str] = None
    assigned_station_id: Optional[str] = None
    linker_capacity: Optional[int] = None
    is_dispatch: Optional[bool] = None
    is_assemble: Optional[bool] = None
    is_dispatch_admin: Optional[bool] = None
    department: Optional[str] = None
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None
    business_name: Optional[str] = None
    alternate_mobile_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    order_credit_limit: Optional[float] = None
    overall_credit_limit: Optional[float] = None
    jobcard: Optional[bool] = None


class UserSelfUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    password: Optional[str] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class User(UserBase):
    user_id: str
    master_admin_id: Optional[str] = None
    assigned_station_id: Optional[str] = None
    assigned_station_name: Optional[str] = None
    linker_capacity: Optional[int] = None
    global_qr_number: Optional[int] = None
    part_name: Optional[str] = None
    password: Optional[str] = None
    step: Optional[int] = None
    qrcode: Optional[str] = None

class UserResponse(BaseModel):
    users: list[User]
    page: int
    total_pages: int
    total_count: int

class StationAssignment(BaseModel):
    station_id: str
    timestamp: datetime

class StationBase(BaseModel):
    name: str
    process: Optional[str] = None
    process_id: Optional[str] = None
    active: bool
    comment: Optional[str] = None
    linker_capacity: Optional[int] = None
    global_qr_number: Optional[int] = None
    part_id: Optional[str] = None
    master_admin_id: Optional[str] = None
    is_dispatch: Optional[bool] = False
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None

    @model_validator(mode='after')
    def check_qr_capacity(self) -> 'StationBase':
        if self.global_qr_number is not None and self.linker_capacity is not None:
            if self.global_qr_number > self.linker_capacity:
                raise ValueError('global_qr_number cannot be greater than linker_capacity')
        return self

class StationCreate(StationBase):
    pass

class StationUpdate(BaseModel):
    name: Optional[str] = None
    process: Optional[str] = None
    process_id: Optional[str] = None
    active: Optional[bool] = None
    comment: Optional[str] = None
    linker_capacity: Optional[int] = None
    global_qr_number: Optional[int] = None
    is_dispatch: Optional[bool] = None

    @model_validator(mode='after')
    def check_qr_capacity(self) -> 'StationUpdate':
        if self.global_qr_number is not None and self.linker_capacity is not None:
            if self.global_qr_number > self.linker_capacity:
                raise ValueError('global_qr_number cannot be greater than linker_capacity')
        return self

class Station(StationBase):
    station_id: str
    qrcode: str
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None

class ShiftBase(BaseModel):
    name: str
    start_time: time
    end_time: time
    active: bool

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    active: Optional[bool] = None

class Shift(ShiftBase):
    shift_id: str


class ScannerProcessDetailCreate(BaseModel):
    qr_id: str

class InspectorProcessUpdate(BaseModel):
    qr_id: str
    inspection_status: str
    reject_reason: Optional[str] = None

class ScannerProcessDetail(ScannerProcessDetailCreate):
    scan_id: str
    station_id: str
    scanner_id: str
    inspection_status: Optional[str] = "OKAY"
    start_time: datetime
    end_time: Optional[datetime] = None
    inspector_id: Optional[str] = None
    station_name: Optional[str] = None
    station_comment: Optional[str] = None
    scanner_name: Optional[str] = None
    inspector_name: Optional[str] = None
    reject_reason: Optional[str] = None
    rejection_image: Optional[str] = None
    is_latest: bool = True
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None
    part_name: Optional[str] = None
    station_jobcard_id: Optional[str] = None  # ID of the station-based (no-QR) jobcard owning this scan

class AssemblyLinkCreate(BaseModel):
    qr_ids: list[str]

class AssemblyProcessDetail(BaseModel):
    assembly_id: str
    qr_ids: list[Any]
    process_name: str
    station_id: str
    linker_id: str
    inspection_status: Optional[str] = "OKAY"
    start_time: datetime
    end_time: Optional[datetime] = None
    inspector_id: Optional[str] = None
    station_name: Optional[str] = None
    station_comment: Optional[str] = None
    linker_name: Optional[str] = None
    inspector_name: Optional[str] = None
    reject_reason: Optional[str] = None
    is_latest: bool = True
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None

class DispatchProcessDetail(BaseModel):
    dispatch_id: str
    qr_ids: list[Any]
    process_name: str
    station_id: str
    linker_id: str
    inspection_status: Optional[str] = "OKAY"
    start_time: datetime
    end_time: Optional[datetime] = None
    inspector_id: Optional[str] = None
    station_name: Optional[str] = None
    station_comment: Optional[str] = None
    linker_name: Optional[str] = None
    inspector_name: Optional[str] = None
    reject_reason: Optional[str] = None
    is_latest: bool = True
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None

class PartBase(BaseModel):
    name: str
    type: str
    active: bool
    is_assemble: Optional[bool] = False
    is_dispatch_admin: Optional[bool] = False
    processes: Optional[list[str]] = []       # List of process names to auto-create
    category_id: Optional[str] = None          # Scoped product category ID
    category_name: Optional[str] = None        # Auto-resolved category name

class PartCreate(PartBase):
    pass

class PartUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    active: Optional[bool] = None
    is_assemble: Optional[bool] = None
    is_dispatch_admin: Optional[bool] = None
    processes: Optional[list[str]] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None

class Part(PartBase):
    part_id: str

class JobCardBase(BaseModel):
    jobcard_no: Optional[str] = None
    jobcard_date: str
    part_composition: str
    quantity: int
    station_ids: Optional[list[str]] = []  # List of target station IDs
    plant_id: Optional[str] = None
    process_id: Optional[str] = None
    process_name: Optional[str] = None
    product_model_name: Optional[str] = None
    currency: Optional[str] = "INR"
    auto_scan: Optional[bool] = False

class JobCardCreate(JobCardBase):
    pass

class JobCardAssembleCreate(BaseModel):
    job_card: JobCardCreate
    variant_sku: str

class JobCardStatusUpdate(BaseModel):
    status: str

class QRBulkDelete(BaseModel):
    qr_ids: list[str]

class JobCardImportPreview(BaseModel):
    qr_id: str
    is_valid: bool = True
    error: Optional[str] = None

class JobCardReverseCreate(BaseModel):
    jobcard_no: Optional[str] = None
    jobcard_date: str
    part_composition: str
    qr_ids: list[str]
    station_ids: Optional[list[str]] = []
    variant_sku: Optional[str] = None
    product_model_name: Optional[str] = None
    auto_scan: Optional[bool] = False

class JobCardReverseSequence(BaseModel):
    start_id: str
    quantity: int

class AssetCategoryBase(BaseModel):
    name: str

class AssetCategoryCreate(AssetCategoryBase):
    pass

class AssetCategory(AssetCategoryBase):
    category_id: str
    created_by: str
    created_at: datetime

class AssetSubCategoryBase(BaseModel):
    name: str
    category_id: str

class AssetSubCategoryCreate(AssetSubCategoryBase):
    pass

class AssetSubCategory(AssetSubCategoryBase):
    subcategory_id: str
    category_name: Optional[str] = None
    created_by: str
    created_at: datetime

class AssetBase(BaseModel):
    name: str
    asset_no: str
    model: str
    purchase_date: str
    cost: float
    brand: str
    category_id: str
    subcategory_id: Optional[str] = None
    is_warranty: Optional[bool] = None
    is_guarantee: Optional[bool] = None
    warranty_expiry_date: Optional[str] = None
    color: Optional[str] = None
    guarantee_date: Optional[str] = None
    expire_date: Optional[str] = None
    comment: Optional[str] = None
    status: str = "Active"
    maintenance_period: Optional[str] = None

    @model_validator(mode='after')
    def validate_warranty_info(self) -> 'AssetBase':
        has_flag = self.is_warranty or self.is_guarantee
        has_date = bool(self.warranty_expiry_date)
        
        if has_flag and not has_date:
            raise ValueError('warranty_expiry_date is required if is_warranty or is_guarantee is true')
        if has_date and not has_flag:
            raise ValueError('is_warranty or is_guarantee must be true if warranty_expiry_date is provided')
        return self

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    asset_no: Optional[str] = None
    model: Optional[str] = None
    purchase_date: Optional[str] = None
    cost: Optional[float] = None
    brand: Optional[str] = None
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    is_warranty: Optional[bool] = None
    is_guarantee: Optional[bool] = None
    warranty_expiry_date: Optional[str] = None
    color: Optional[str] = None
    guarantee_date: Optional[str] = None
    expire_date: Optional[str] = None
    comment: Optional[str] = None
    status: Optional[str] = None
    maintenance_period: Optional[str] = None

    @model_validator(mode='after')
    def validate_warranty_info(self) -> 'AssetUpdate':
        # For updates, we only validate if at least one of the fields is provided
        # Note: This is a bit complex for partial updates because we don't have the existing data here.
        # However, we can validate the incoming payload for consistency.
        has_flag = self.is_warranty or self.is_guarantee
        has_date = bool(self.warranty_expiry_date)
        
        if has_flag and self.warranty_expiry_date is not None and not has_date:
             raise ValueError('warranty_expiry_date cannot be empty if is_warranty or is_guarantee is true')
        
        # If both flag and date are in the update payload, they must be consistent
        if has_flag is not None and has_date is not None:
            if has_flag and not has_date:
                raise ValueError('warranty_expiry_date is required if is_warranty or is_guarantee is true')
            if has_date and not has_flag:
                raise ValueError('is_warranty or is_guarantee must be true if warranty_expiry_date is provided')
        return self

class Asset(AssetBase):
    asset_id: str
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    invoice_pdf: Optional[str] = None
    images: list[str] = []
    master_admin_id: str
    master_admin_name: str
    created_at: datetime
    is_assigned: bool = False
    submission_status: Optional[str] = None

class JobCard(JobCardBase):
    jobcard_id: str
    part_id: str
    part_model: str
    created_by: str
    created_by_name: Optional[str] = None
    created_by_role: Optional[str] = None
    created_by_department: Optional[str] = None
    created_at: datetime
    status: str
    completion_percentage: Optional[float] = 0.0
    process_wise_completion: Optional[list[dict]] = []
    # Variant linkage
    variant_id: Optional[str] = None
    variant_sku: Optional[str] = None
    # Hierarchy
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    submodel_id: Optional[str] = None
    submodel_name: Optional[str] = None
    # Variant attributes
    color: Optional[str] = None
    size: Optional[int] = None
    size_name: Optional[str] = None
    mrp: Optional[dict[str, float]] = None
    finish: Optional[str] = None
    certification: Optional[list[str]] = None
    visor_type: Optional[str] = None
    spoiler: Optional[str] = None
    chinstrap_lock: Optional[str] = None
    pinlock: Optional[str] = None
    carton_box_size: Optional[int] = None
    carton_barcode: Optional[str] = None
    currency: Optional[str] = "INR"
    is_active: Optional[bool] = False

class JobCardResponse(BaseModel):
    cards: list[JobCard]
    page: int
    total_pages: int
    total_count: int

class ProcessBase(BaseModel):
    name: str
    part_id: Optional[str] = None     # Optional in base, populated or required inside operations
    part_name: Optional[str] = None   # Auto-resolved part name
    step: Optional[int] = None        # Process step sequence number

class ProcessCreate(ProcessBase):
    pass

class Process(ProcessBase):
    process_id: str
    created_by: str
    created_at: datetime


class ReasonBase(BaseModel):
    name: str
    process_id: Optional[str] = None     # Optional/required scoped process
    process_name: Optional[str] = None   # Auto-resolved process name

class ReasonCreate(ReasonBase):
    pass

class Reason(ReasonBase):
    reason_id: str
    created_by: str
    created_at: datetime



class DashboardStats(BaseModel):
    OKAY: int
    REWORKED: int
    REJECTED: int
    TOTAL: int

class TimeSeriesEntry(DashboardStats):
    date: str

class DashboardTimeSeries(BaseModel):
    twelve_h: list[TimeSeriesEntry] = Field(alias="12h")
    twenty_four_h: list[TimeSeriesEntry] = Field(alias="24h")
    seven_d: list[TimeSeriesEntry] = Field(alias="7d")
    thirty_d: list[TimeSeriesEntry] = Field(alias="30d")

    class Config:
        populate_by_name = True

class DashboardSummary(BaseModel):
    summary: DashboardStats
    time_series: DashboardTimeSeries
    total_linked: Optional[int] = None
    parts_summary: Optional[list[Any]] = None
    job_cards_summary: Optional[list[Any]] = None
    total_job_card_quantity: Optional[int] = None

class JobCardHistoryEntry(BaseModel):
    type: str = "Job Card"
    jobcard_no: Optional[str] = None
    jobcard_id: Optional[str] = None
    jobcard_date: Optional[str] = None
    part_composition: Optional[str] = None
    quantity: Optional[int] = None
    status: Optional[str] = None
    part_id: Optional[str] = None
    part_model: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by_name: Optional[str] = None
    created_by_role: Optional[str] = None
    created_by_department: Optional[str] = None
    # Variant linkage
    variant_id: Optional[str] = None
    variant_sku: Optional[str] = None
    # Hierarchy
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    submodel_id: Optional[str] = None
    submodel_name: Optional[str] = None
    # Variant attributes
    color: Optional[str] = None
    size: Optional[int] = None
    size_name: Optional[str] = None
    mrp: Optional[dict[str, float]] = None
    finish: Optional[str] = None
    certification: Optional[list[str]] = None
    visor_type: Optional[str] = None
    spoiler: Optional[str] = None
    currency: Optional[str] = "INR"
    chinstrap_lock: Optional[str] = None
    pinlock: Optional[str] = None
    carton_box_size: Optional[int] = None
    carton_barcode: Optional[str] = None
    product_model_name: Optional[str] = None

class ScannerHistoryEntry(BaseModel):
    type: str = "Reader Process"
    qr_id: Optional[str] = None
    scan_id: Optional[str] = None
    process_name: Optional[str] = None
    station_name: Optional[str] = None
    station_id: Optional[str] = None
    scanner_id: Optional[str] = None
    scanner_name: Optional[str] = None
    inspection_status: Optional[str] = None
    is_latest: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    inspector_id: Optional[str] = None
    inspector_name: Optional[str] = None
    reject_reason: Optional[str] = None
    rejection_image: Optional[str] = None
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None
    part_name: Optional[str] = None
    station_jobcard_id: Optional[str] = None


class AssemblyHistoryEntry(BaseModel):
    type: str = "Assembly Process"
    assembly_id: Optional[str] = None
    process_name: Optional[str] = None
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    linker_id: Optional[str] = None
    linker_name: Optional[str] = None
    inspection_status: Optional[str] = None
    is_latest: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    inspector_id: Optional[str] = None
    inspector_name: Optional[str] = None
    reject_reason: Optional[str] = None
    qr_ids: Optional[list[Any]] = None
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None

class DispatchHistoryEntry(BaseModel):
    type: str = "Dispatch Process"
    dispatch_id: Optional[str] = None
    process_name: Optional[str] = None
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    linker_id: Optional[str] = None
    linker_name: Optional[str] = None
    inspection_status: Optional[str] = None
    is_latest: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    inspector_id: Optional[str] = None
    inspector_name: Optional[str] = None
    reject_reason: Optional[str] = None
    qr_ids: Optional[list[Any]] = None
    plant_id: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None

class DispatchDetailEntry(BaseModel):
    type: str = "Dispatch Detail"
    data: Any

QRHistoryEntry = Union[JobCardHistoryEntry, ScannerHistoryEntry, AssemblyHistoryEntry, DispatchHistoryEntry, DispatchDetailEntry]

class QRProductInfo(BaseModel):
    qr_id: str
    part_id: Optional[str] = None
    part_name: str
    created_at: Optional[datetime] = None
    model_name: Optional[str] = None
    product_model_name: Optional[str] = None

class QRComponent(BaseModel):
    product: QRProductInfo
    history: list[QRHistoryEntry]

class QRHistoryTree(BaseModel):
    components: list[QRComponent]
    assembly_history: list[QRHistoryEntry]

class AssetStatusSummary(BaseModel):
    total: int
    assigned: int
    available: int

class AssetCategorySummary(BaseModel):
    category_id: str
    category_name: str
    count: int

class AssetWarrantySummary(BaseModel):
    under_warranty: int
    under_guarantee: int
    no_warranty: int

class AssetDashboard(BaseModel):
    status_summary: AssetStatusSummary
    category_summary: list[AssetCategorySummary]
    warranty_summary: AssetWarrantySummary
    recent_submissions: list[Any]


# ─── KIOSK SCHEMAS ─────────────────────────────────────────────

class KioskTheme(BaseModel):
    primary_color: str
    secondary_color: str
    background_color: str
    logo_url: str
    splash_image_url: str

class KioskConfigData(BaseModel):
    device_id: str
    theme: KioskTheme
    is_update_mandatory: bool
    apk_download_url: str
    admin_pin: Optional[str] = None

class KioskConfigResponse(BaseModel):
    status: str = "success"
    data: Optional[KioskConfigData] = None

class KioskVerifyPinRequest(BaseModel):
    pin: str

class KioskVerifyPinResponseData(BaseModel):
    is_valid: bool
    access_granted_until: str

class KioskVerifyPinResponse(BaseModel):
    status: str
    message: str
    data: KioskVerifyPinResponseData

class KioskCreate(BaseModel):
    admin_pin: str
    theme: KioskTheme
    is_update_mandatory: bool
    apk_download_url: str

class KioskUpdate(BaseModel):
    admin_pin: Optional[str] = None
    theme: Optional[KioskTheme] = None
    is_update_mandatory: Optional[bool] = None
    apk_download_url: Optional[str] = None

# ─── PRODUCT MASTER SCHEMAS ────────────────────────────────────

class ProductCategoryCreate(BaseModel):
    name: str
    is_active: bool = True

class ProductCategoryUpdate(BaseModel):
    is_active: Optional[bool] = None

class ProductSubCategoryCreate(BaseModel):
    name: str
    category_id: str
    is_active: bool = True

class ProductSubCategoryUpdate(BaseModel):
    is_active: Optional[bool] = None

class ProductBrandCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class ProductBrandUpdate(BaseModel):
    is_active: Optional[bool] = None

class ProductModelCreate(BaseModel):
    name: str
    brand_id: str
    category_id: Optional[str] = None
    subcategory_id: str
    is_active: bool = True
    chinstrap_lock: Optional[str] = None
    box_weight: Optional[float] = None
    box_dimension: Optional[str] = None
    carton_weight: Optional[float] = None
    carton_dimension: Optional[str] = None
    certification: list[str] = []

class ProductModelUpdate(BaseModel):
    is_active: Optional[bool] = None
    chinstrap_lock: Optional[str] = None
    box_weight: Optional[float] = None
    box_dimension: Optional[str] = None
    carton_weight: Optional[float] = None
    carton_dimension: Optional[str] = None
    certification: Optional[list[str]] = None

class ProductSubModelCreate(BaseModel):
    name: str
    model_id: str
    is_active: bool = True
    # Variant fields stored on submodel
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    product_images: list[str] = []
    visor_type: Optional[str] = None
    spoiler: Optional[str] = None
    pinlock: Optional[str] = None
    style: Optional[str] = None

class ProductSubModelUpdate(BaseModel):
    is_active: Optional[bool] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    product_images: Optional[list[str]] = None
    visor_type: Optional[str] = None
    spoiler: Optional[str] = None
    pinlock: Optional[str] = None
    style: Optional[str] = None

class ProductVariantCreate(BaseModel):
    sku_no: str
    submodel_id: str
    gs1_barcode: Optional[str] = None
    carton_barcode: Optional[str] = None
    color: Optional[str] = None
    size_name: Optional[str] = None
    size: Optional[int] = None
    finish: Optional[str] = None
    product_images: list[str] = []
    mrp: Optional[dict[str, float]] = None
    is_active: bool = True

class ProductVariantUpdate(BaseModel):
    is_active: Optional[bool] = None
    gs1_barcode: Optional[str] = None
    carton_barcode: Optional[str] = None
    color: Optional[str] = None
    size_name: Optional[str] = None
    size: Optional[int] = None
    finish: Optional[str] = None
    product_images: Optional[list[str]] = None
    mrp: Optional[dict[str, float]] = None


class PlantBase(BaseModel):
    plant_name: str
    plant_address: str
    status: str = "Active"
    unit: Optional[str] = None
    location_name: Optional[str] = None
    pincode: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    gstin: Optional[str] = None

class PlantCreate(PlantBase):
    pass

class PlantUpdate(BaseModel):
    status: Optional[str] = None
    plant_name: Optional[str] = None
    plant_address: Optional[str] = None
    unit: Optional[str] = None
    location_name: Optional[str] = None
    pincode: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    gstin: Optional[str] = None

class Plant(PlantBase):
    plant_id: str
    status: str = "Active"


# ─── DEALER SIGNUP REQUEST SCHEMAS ──────────────────────────────

class DealerSignupRequestBase(BaseModel):
    # Contact Info
    contact_name: str
    email: str
    mobile_number: str

    # Company
    business_name: str

class DealerSignupRequestCreate(DealerSignupRequestBase):
    pass

class DealerSignupRequestUpdateStatus(BaseModel):
    approve: Union[bool, str]
    password: Optional[str] = None

    @field_validator('approve', mode='before')
    @classmethod
    def coerce_approve_status(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            val_lower = v.strip().lower()
            if val_lower in ["true", "approved", "approve", "yes", "1"]:
                return True
            elif val_lower in ["false", "rejected", "reject", "no", "0"]:
                return False
            raise ValueError("Approve status must be a boolean or a valid string ('Approved', 'Rejected', etc.)")
        return bool(v)

class DealerSignupRequest(DealerSignupRequestBase):
    request_id: str
    status: str = "Pending"
    created_at: datetime
    updated_at: datetime
    processed_by: Optional[str] = None


# ─── B2B INWARD SCHEMAS ──────────────────────────────────────────

class B2BInwardProductCreate(BaseModel):
    variant_id: str
    dealer_price: float
    currency: Optional[str] = "INR"
    quantity: Optional[int] = None
    reference_no: Optional[str] = None
    is_individual: bool = True
    is_carton: bool = False
    is_featured: bool = False
    is_new_arrival: bool = False
    is_best_seller: bool = False
    is_active: bool = True

class B2BInwardProductUpdate(BaseModel):
    dealer_price: Optional[float] = None
    currency: Optional[str] = None
    quantity: Optional[int] = None
    reference_no: Optional[str] = None
    is_individual: Optional[bool] = None
    is_carton: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_new_arrival: Optional[bool] = None
    is_best_seller: Optional[bool] = None
    is_active: Optional[bool] = None

class B2BInwardProduct(BaseModel):
    inward_id: str
    variant_id: str
    sku_no: str
    dealer_price: float
    currency: str = "INR"
    quantity: Optional[int] = None
    reference_no: Optional[str] = None
    is_individual: bool
    is_carton: bool
    is_featured: bool
    is_new_arrival: bool
    is_best_seller: bool
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

class B2BInwardCardResponse(BaseModel):
    inward_id: str
    variant_id: str
    sku_no: str
    name: str
    image: Optional[str] = None
    dealer_price: float
    currency: str = "INR"
    quantity: Optional[int] = None
    reference_no: Optional[str] = None
    mrp: Optional[float] = None
    color: Optional[str] = None
    size: Optional[int] = None
    size_name: Optional[str] = None
    carton_box_size: Optional[int] = None
    is_individual: bool
    is_carton: bool
    is_featured: bool
    is_new_arrival: bool
    is_best_seller: bool
    is_active: bool
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    subcategory_id: Optional[str] = None
    subcategory_name: Optional[str] = None
    brand_id: Optional[str] = None
    brand_name: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    submodel_id: Optional[str] = None
    submodel_name: Optional[str] = None

class B2BSubmodelCardVariant(BaseModel):
    variant_id: str
    sku_no: str
    color: Optional[str] = None
    size: Optional[int] = None
    size_name: Optional[str] = None
    dealer_price: float
    currency: str = "INR"
    quantity: Optional[int] = None
    inward_id: str
    is_active: bool
    model_images: list[str] = []
    product_images: list[str] = []

class B2BSubmodelCardResponse(BaseModel):
    submodel_id: str
    name: str
    image: Optional[str] = None
    starting_price: float
    currency: str = "INR"
    total_variants: int
    is_active: bool
    is_featured: bool
    is_new_arrival: bool
    is_best_seller: bool
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    subcategory_id: Optional[str] = None
    subcategory_name: Optional[str] = None
    brand_id: Optional[str] = None
    brand_name: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    variants: list[B2BSubmodelCardVariant] = []

class B2BInwardDetailResponse(BaseModel):
    submodel_detail: dict
    variants: list[dict] = []

class B2BCartItemAdd(BaseModel):
    inward_id: str
    quantity: int = 1

class B2BCartItemUpdate(BaseModel):
    quantity: int

class B2BCartItemResponse(BaseModel):
    inward_id: str
    variant_id: str
    sku_no: str
    name: str
    image: Optional[str] = None
    dealer_price: float
    currency: str = "INR"
    mrp: Optional[float] = None
    quantity: int
    subtotal: float
    is_individual: bool
    is_carton: bool
    quantity_invoiced: Optional[int] = 0
    quantity_backordered: Optional[int] = 0


class B2BCartResponse(BaseModel):
    items: list[B2BCartItemResponse]
    total_items: int
    total_price: float

# ─── DEALER COMPANY ADDRESS SCHEMAS ─────────────────────────────

class DealerCompanyAddressBase(BaseModel):
    address_id: Optional[str] = None
    name: Optional[str] = None
    business_name: Optional[str] = None
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    alternate_mobile: Optional[str] = None
    web: Optional[str] = None
    business_email: Optional[str] = None
    business_mobile: Optional[str] = None
    address_type: Optional[str] = None  # e.g., "business", "billing", "shipping"
    is_business_address: Optional[bool] = False

class DealerCompanyAddressCreate(DealerCompanyAddressBase):
    pass

class DealerCompanyAddressResponse(DealerCompanyAddressBase):
    user_id: str
    updated_at: datetime


class B2BCheckoutRequest(BaseModel):
    address_id: Optional[str] = None
    shipping_address_id: Optional[str] = None
    billing_address_id: Optional[str] = None
    payment_type: Optional[str] = None
    coupon_code: Optional[str] = None
    coins_to_redeem: Optional[float] = None  # coins dealer wants to apply as discount


class B2BCheckoutSummaryResponse(BaseModel):
    company_address: Optional[DealerCompanyAddressBase] = None
    shipping_address: Optional[DealerCompanyAddressBase] = None
    billing_address: Optional[DealerCompanyAddressBase] = None
    items: list[B2BCartItemResponse]
    total_items: int
    subtotal: float
    discount_applied: float
    coin_discount: float = 0.0
    total_price: float
    coupon_code: Optional[str] = None
    coin_balance: float = 0.0
    potential_coins_earned: float = 0.0


# ─── B2B ORDER SCHEMAS ──────────────────────────────────────────

class B2BOrderCreate(BaseModel):
    pass

class B2BOrderSummary(BaseModel):
    """Lightweight order representation used in list responses."""
    order_id: str
    user_id: str
    ordered_by: Optional[str] = None
    company_address: Optional[DealerCompanyAddressBase] = None
    shipping_address: Optional[DealerCompanyAddressBase] = None
    billing_address: Optional[DealerCompanyAddressBase] = None
    total_items: int
    subtotal: Optional[float] = None
    discount_applied: Optional[float] = None
    coin_discount: Optional[float] = None
    total_price: float
    status: str
    payment_type: Optional[str] = None
    coupon_code: Optional[str] = None
    coins_earned: Optional[float] = None
    coins_redeemed: Optional[float] = None
    dealer_coin_balance: Optional[float] = None   # current wallet balance at time of fetch
    payment_status: Optional[str] = "Unpaid"
    created_at: datetime

class B2BInvoiceItem(BaseModel):
    inward_id: str
    sku_no: str
    name: str
    quantity: int
    dealer_price: float
    subtotal: float
    currency: Optional[str] = "INR"

class B2BInvoice(BaseModel):
    invoice_id: str
    items: list[B2BInvoiceItem]
    subtotal: float
    tax_type: str
    tax_rate: float
    tax_amount: float
    total_with_tax: float
    created_at: datetime

class B2BOrderResponse(BaseModel):
    order_id: str
    user_id: str
    ordered_by: Optional[str] = None
    company_address: DealerCompanyAddressBase
    shipping_address: Optional[DealerCompanyAddressBase] = None
    billing_address: Optional[DealerCompanyAddressBase] = None
    items: list[B2BCartItemResponse]
    total_items: int
    subtotal: Optional[float] = None
    discount_applied: Optional[float] = None
    coin_discount: Optional[float] = None
    total_price: float
    status: str = "Pending"
    payment_type: Optional[str] = None
    coupon_code: Optional[str] = None
    admin_note: Optional[str] = None
    cancel_reason: Optional[str] = None
    dispatch_details: Optional[dict] = None
    status_history: Optional[list] = None
    created_at: datetime
    updated_at: datetime
    po_url: Optional[str] = None
    tracking_url: Optional[str] = None
    coins_earned: Optional[float] = None
    coins_redeemed: Optional[float] = None
    dealer_coin_balance: Optional[float] = None   # live wallet balance at time of fetch
    payment_status: Optional[str] = "Unpaid"
    invoices: list[B2BInvoice] = []
    has_backorder: bool = False



# ─── B2B ADMIN ORDER MANAGEMENT SCHEMAS ─────────────────────────

# Valid order lifecycle statuses
B2B_ORDER_STATUSES = ["Pending", "Confirmed", "Processing", "Dispatched", "Delivered", "Cancelled"]

class B2BOrderStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None           # admin note for this transition

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = ["Pending", "Confirmed", "Processing", "Dispatched", "Delivered", "Cancelled"]
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v

class B2BOrderCancelRequest(BaseModel):
    reason: str

class B2BOrderDispatchUpdate(BaseModel):
    courier_name: str
    tracking_number: str
    estimated_delivery: Optional[str] = None   # ISO date string e.g. "2026-05-30"
    note: Optional[str] = None

class B2BOrderNoteUpdate(BaseModel):
    note: str

class B2BOrderBulkStatusUpdate(BaseModel):
    order_ids: list[str]
    status: str
    note: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = ["Confirmed", "Processing", "Dispatched", "Delivered", "Cancelled"]
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v

class B2BOrderBulkResult(BaseModel):
    updated: list[str]
    failed: list[str]
    message: str


# ─── B2B ADMIN DASHBOARD SCHEMAS ────────────────────────────────

class B2BSalesSummary(BaseModel):
    total_orders: int
    total_revenue: float
    pending_orders: int
    confirmed_orders: int
    dispatched_orders: int
    delivered_orders: int
    cancelled_orders: int
    avg_order_value: float
    backorder_orders: int


class B2BRevenueTimeSeries(BaseModel):
    date: str
    orders: int
    revenue: float

class B2BTopProduct(BaseModel):
    inward_id: str
    variant_id: str
    sku_no: str
    name: str
    image: Optional[str] = None
    total_quantity_sold: int
    total_revenue: float

class B2BTopDealer(BaseModel):
    user_id: str
    dealer_name: str
    mobile_number: Optional[str] = None
    total_orders: int
    total_spent: float
    last_order_at: Optional[datetime] = None

class B2BDealerSummary(BaseModel):
    total_dealers: int
    active_dealers: int
    inactive_dealers: int
    new_dealers_this_month: int
    dealers_with_orders: int

class B2BProductSummary(BaseModel):
    total_inwarded: int
    active_products: int
    inactive_products: int
    featured_products: int
    new_arrivals: int
    best_sellers: int
    total_categories: int
    total_brands: int

class B2BBackorderedVariant(BaseModel):
    variant_id: str
    sku_no: str
    name: str
    backorder_quantity: int
    available_stock: int
    order_ids: list[str]

class B2BAdminDashboard(BaseModel):
    sales_summary: B2BSalesSummary
    dealer_summary: B2BDealerSummary
    product_summary: B2BProductSummary
    revenue_time_series: list[B2BRevenueTimeSeries]
    top_products: list[B2BTopProduct]
    top_dealers: list[B2BTopDealer]
    recent_orders: list[B2BOrderSummary]
    backordered_variants: list[B2BBackorderedVariant]


# ─── B2B COUPON SCHEMAS ──────────────────────────────────────────

class B2BCouponBase(BaseModel):
    coupon_code: str
    description: Optional[str] = None
    discount_type: str  # "Percentage" or "Flat"
    discount_value: float
    max_discount_value: Optional[float] = None
    minimum_order_value: Optional[float] = None
    is_applicable_product: bool = False
    applicable_product_ids: list[str] = []
    is_applicable_submodel: bool = False
    applicable_submodel_ids: list[str] = []
    is_applicable_dealer: bool = False
    applicable_dealer_ids: list[str] = []
    start_date: datetime
    end_date: datetime
    coupon_limit: Optional[int] = None
    user_usage_limit: Optional[int] = None
    is_active: bool = True

    @model_validator(mode='after')
    def validate_discount_value(self) -> 'B2BCouponBase':
        if self.discount_type == "Percentage" and self.discount_value >= 100:
            raise ValueError('Percentage discount value must be less than 100')
        return self


class B2BCouponCreate(B2BCouponBase):
    pass


class B2BCouponUpdate(BaseModel):
    coupon_code: Optional[str] = None
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    max_discount_value: Optional[float] = None
    minimum_order_value: Optional[float] = None
    is_applicable_product: Optional[bool] = None
    applicable_product_ids: Optional[list[str]] = None
    is_applicable_submodel: Optional[bool] = None
    applicable_submodel_ids: Optional[list[str]] = None
    is_applicable_dealer: Optional[bool] = None
    applicable_dealer_ids: Optional[list[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    coupon_limit: Optional[int] = None
    user_usage_limit: Optional[int] = None
    is_active: Optional[bool] = None


class B2BCouponResponse(B2BCouponBase):
    coupon_id: str
    created_at: datetime
    updated_at: datetime
    created_by: str


# ─── COIN / REWARDS SYSTEM SCHEMAS ──────────────────────────────

class CoinConfigUpdate(BaseModel):
    """Admin sets the earn-rate (% of order total_price) and optional coin-to-INR rate."""
    earn_rate_percent: Optional[float] = None   # e.g. 2.0 → dealer earns 2% of order as coins
    coin_to_inr: Optional[float] = None          # how many INR is 1 coin worth (default 1)
    is_active: Optional[bool] = None             # toggle coin rewards on/off globally

class CoinConfigResponse(BaseModel):
    earn_rate_percent: float = 0.0
    coin_to_inr: float = 1.0
    is_active: bool = True
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

class CoinWalletResponse(BaseModel):
    user_id: str
    coin_balance: float = 0.0
    total_earned: float = 0.0
    total_redeemed: float = 0.0
    last_updated: Optional[datetime] = None

class CoinTransactionResponse(BaseModel):
    txn_id: str
    user_id: str
    txn_type: str                  # "CREDIT" | "DEBIT"
    coins: float
    reference_id: Optional[str] = None   # order_id
    note: Optional[str] = None
    created_at: datetime

class CoinRedeemRequest(BaseModel):
    coins_to_redeem: float         # coins the dealer wants to spend on this order

# ─── B2B LIMITS SCHEMAS ──────────────────────────────────────────

class B2BLimitsUpdate(BaseModel):
    order_credit_limit: Optional[float] = None
    overall_credit_limit: Optional[float] = None

class B2BDefaultLimitsResponse(BaseModel):
    order_credit_limit: Optional[float] = None
    overall_credit_limit: Optional[float] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

class DealerCreditStatusResponse(BaseModel):
    user_id: str
    business_name: Optional[str] = None
    order_credit_limit: Optional[float] = None
    overall_credit_limit: Optional[float] = None
    outstanding_amount: float
    remaining_credit: Optional[float] = None


# ─── B2B GST SETTING SCHEMAS ─────────────────────────────────────

class B2BGstSettingCreate(BaseModel):
    state: str
    tax_type: str
    percent: float
    is_default: bool = False

class B2BGstSettingUpdate(BaseModel):
    state: Optional[str] = None
    tax_type: Optional[str] = None
    percent: Optional[float] = None
    is_default: Optional[bool] = None

class B2BGstSettingResponse(BaseModel):
    setting_id: str
    state: str
    tax_type: str
    percent: float
    is_default: bool = False
    created_by: str
    created_at: datetime
    updated_at: datetime


class B2BOrderPaymentStatusUpdate(BaseModel):
    payment_status: str

    @field_validator("payment_status")
    @classmethod
    def validate_payment_status(cls, v: str) -> str:
        allowed = ["Paid", "Unpaid", "Refunded"]
        if v not in allowed:
            raise ValueError(f"payment_status must be one of {allowed}")
        return v


class B2BInvoicePreviewResponse(BaseModel):
    items_to_invoice: list[B2BInvoiceItem]
    items_to_backorder: list[B2BCartItemResponse]
    subtotal: float
    tax_type: str
    tax_rate: float
    tax_amount: float
    total_with_tax: float


class B2BInvoiceManualItem(BaseModel):
    inward_id: str
    quantity: int

class B2BInvoiceManualRequest(BaseModel):
    items: list[B2BInvoiceManualItem]




