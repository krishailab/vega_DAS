# Linker API Documentation

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

### Get My Linking History
**Endpoint**: `GET /scan/my-history`
**Description**: View all your past assembly activities.

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
**Description**: Linkers must scan the Assemble Line QR at their station.
**Payload**:
```json
{
  "station_id": "ASL26AA0001",
  "timestamp": "2026-04-26T08:05:00"
}
```



### Step 3: Link Parts (Assembly)
**Endpoint**: `POST /scan/link`
**Description**: Links multiple QR IDs together into a flat assembly record.
**Payload**:
```json
{
  "qr_ids": ["PRD26AA0001", "PRD26AA0002", "PRD26AA0003"]
}
```
**Notes**:
- All QR IDs in the list must belong to distinct part models (e.g., 1 Shell, 1 Visor, 1 Belt).
- The number of QR IDs must exactly match the station's `linker_capacity` (if set) or your personal `linker_capacity`.
- This creates a shared assembly record for all listed IDs.

## 2. Validation Rules
- All components must have successfully completed their individual Scanner stages.
- If any component was previously marked `REWORKED`, the whole assembly will be flagged as `PENDING` for an Inspector to verify.
