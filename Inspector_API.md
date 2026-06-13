# Inspector API Documentation

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

### Get My Inspection History
**Endpoint**: `GET /scan/my-history`
**Description**: View all your past quality control activities.

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

## 2. Daily Workflow

### Step 1: Clock-in (Station Assignment)
**Endpoint**: `POST /users/assign-station`
**Description**: Inspectors scan either a Machine QR or Assemble Line QR.

## 2. Quality Control

### Resolve Pending / Mark Defects
**Endpoint**: `PUT /scan/inspect`
**Content-Type**: `multipart/form-data`
**Description**: Clears a `PENDING` flag or creates a defect record.
**Form Fields**:
* `qr_id`: The ID of the part or any ID from an assembly.
* `inspection_status`: `OKAY`, `REWORKED`, or `REJECTED`.
* `reject_reason` (Optional): Text describing the defect.
* `image` (File/Optional): Mandatory if status is `REJECTED`.

**Status Meanings**:
- **OKAY**: Clears the flag, allows the part to move to the next stage.
- **REWORKED**: Part must be re-scanned at the previous station.
- **REJECTED**: Marks the part as `SCRAPPED`. It is permanently locked.


## 4. Traceability

### Get Product History
**Endpoint**: `GET /scan/history/{qr_id}`
**Description**: Retrieves the full lifecycle of a part, including every scan, rework, and linked component.
