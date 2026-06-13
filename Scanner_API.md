# Scanner API Documentation

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

### Get My Scan History
**Endpoint**: `GET /scan/my-history`
**Description**: View all your past scans and their statuses.

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
**Description**: Scanners must scan the Machine QR at their station before starting work.
**Payload**:
```json
{
  "station_id": "MCH26AA0001",
  "timestamp": "2026-04-26T08:05:00"
}
```

### Step 2: Scan Part
**Endpoint**: `POST /scan/`
**Description**: Scan each physical part after processing.
**Payload**:
```json
{
  "qr_id": "PRD26AA0001"
}
```
**Notes**: 
- The process name is automatically inherited from the assigned Machine.
- If the part was previously marked as `REWORKED`, this scan will trigger a `PENDING` status for an Inspector to verify.

## 2. Status Indicators
- **Implicit OK**: If the app flashes green, the scan is successful. If no Inspector intervenes, the part is considered OK and moves to the next station.
- **Pending/Blocked**: If the app indicates the part is scrapped or already scanned, it cannot be processed further.
