# Master Admin API Documentation

## 1. Common Account APIs

### Login
**Endpoint**: `POST /api/auth/login`
**Content-Type**: `application/x-www-form-urlencoded`
**Fields**:
* `username`: Your Email or Mobile Number
* `password`: Your Password

### Get Profile
**Endpoint**: `GET /users/me`
**Description**: View your own profile details.

### Update Profile
**Endpoint**: `PUT /users/{user_id}`
**Payload**:
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "password": "newpassword123"
}
```

## 2. Sub-User Management

### Create Sub-User
**Endpoint**: `POST /users/`
**Description**: Creates a Scanner, Linker, or Inspector for the organization.
**Payload**:
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "age": 28,
  "gender": "F",
  "blood_group": "A+",
  "employee_id": "VEGA2005",
  "mobile_number": "9123456780",
  "email":"veg@hjs.com",
  "role": "Scanner", // or "Linker" or "Inspector"
  "password": "scannerpass123",
  "assigned_station_id": "STN26AA0001" // Optional
}
```

### Get Organization Users
**Endpoint**: `GET /users/`
**Filter**: `?role=Scanner` (Optional)

### View Sub-User History
**Endpoint**: `GET /scan/user-history/{user_id}`
**Description**: Monitor all activities (scans, links, inspections) of a specific sub-user.

## 2. Infrastructure Management

### Station Management
* **Create**: `POST /stations/`
* **Get All**: `GET /stations/`
* **Update Station**: `PUT /stations/{station_id}`
* **Delete Station**: `DELETE /stations/{station_id}`
* **Download Station QR PDF**: `GET /stations/{station_id}/download-pdf`

**Create Station Payload**:
```json
{
  "name": "Line A Assembly",
  "process": "Final Assembly",
  "active": true,
  "comment": "Main assembly line",
  "linker_capacity": 4,
  "global_qr_number": 1001
}
```

### Shift Management
* **Create**: `POST /shifts/`
* **Get All**: `GET /shifts/`

## 2. Daily Workflow

### Step 1: Assigned Station
Your station is assigned by your Master Admin. You can view your assigned station in your profile (`GET /users/me`).

## 3. Production Control

### Create Job Card
**Endpoint**: `POST /job-cards/`
**Description**: Initiates a batch of QR codes for a specific model.
**Payload**:
```json
{
  "jobcard_no": "JC-SH-2026",
  "jobcard_date": "2026-04-26",
  "part_composition": "Polycarbonate",
  "quantity": 500
}
```

### Download Job Card QRs
**Endpoint**: `GET /job-cards/{jobcard_id}/download-qrs`
**Description**: Downloads an `.xlsx` file containing all QR IDs for the job.

### Generate Reverse Sequence XLSX
**Endpoint**: `POST /job-cards/reverse-import/generate-sequence`
**Description**: Generates an `.xlsx` file with a sequence of IDs starting from a last known number.
**Payload**:
```json
{
  "start_id": "XXXXXXXXXXXX679",
  "quantity": 10
}
```

## 4. Analytics

### Dashboard Summary
**Endpoint**: `GET /scan/dashboard-summary`
**Response**:
```json
{
  "WIP": 45,
  "FINISHED": 120,
  "SCRAPPED": 5,
  "total": 170
}
```

### Asset Dashboard Summary
**Endpoint**: `GET /assets/dashboard`
**Description**: Real-time status, category distribution, and warranty summary for assets.
**Response**:
```json
{
  "status_summary": { "total": 50, "assigned": 20, "available": 30 },
  "category_summary": [...],
  "warranty_summary": { "under_warranty": 15, "under_guarantee": 5, "no_warranty": 30 }
}
```
