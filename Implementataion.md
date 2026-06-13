```markdown
# Backend Implementation Guide

## 1. Overview
This document provides the technical blueprint for the backend engineering team. It translates the database schema and business rules into actionable API endpoints, expected JSON payloads, and architectural best practices. 

**Tech Stack:**
* **Backend Framework:** Django (with Django REST Framework - DRF) or FastAPI
* **Database:** PostgreSQL
* **API Paradigm:** RESTful JSON APIs

---

## 2. Global Architecture & Best Practices

* **Atomic Transactions:** Any API call that touches multiple tables (especially Assembly and QR generation) must be wrapped in a database transaction (`django.db.transaction.atomic`). If mapping fails, the entire payload must roll back.
* **Stateless vs. Session-based:** Mobile apps (Scanner, Linker, Inspector) will authenticate via JWT. The Shift/Machine mapping should be cached (e.g., via Redis or a lightweight session table) tied to the user's JWT, so the frontend doesn't need to pass `machine_id` with every single part scan.
* **Idempotency:** Scanning endpoints should gracefully handle accidental double-taps by checking if the exact same `qr_id` was processed by the exact same user within a short timeframe.

---

## 3. Core API Endpoints & JSON Payloads

### 3.1 Session & Shift Login APIs
These endpoints map a physical worker to a physical workstation for their shift.

**`POST /api/v1/session/machine-login`**
* **Actor:** Scanner
* **Description:** Logs the scanner into a specific machine.
* **Request Payload:**
```json
{
  "machine_code": "MCH-MOULD-01",
  "shift": "09:00-17:00"
}
```
* **Response (200 OK):**
```json
{
  "message": "Session mapped successfully",
  "session_token": "abc123xyz",
  "machine_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 3.2 Scanner Process APIs
These endpoints handle the continuous looping of individual component processing.

**`POST /api/v1/process/scan-part`**
* **Actor:** Scanner
* **Description:** Records that a part has completed a specific stage. Creates a row in `SCANNER_PROCESS_DETAIL`.
* **Request Payload:**
```json
{
  "qr_id": "QR-SH-001",
  "machine_id": "550e8400-e29b-41d4-a716-446655440000",
  "start_time": "2026-04-25T09:15:00Z"
}
```
* **Backend Logic:** 1. Validate `qr_id` is not `SCRAPPED` or already processed for this stage without a `REWORK` flag.
  2. Validate previous stage `inspection_status` is not `PENDING` or `REJECTED`.
* **Response (201 Created):**
```json
{
  "status": "success",
  "message": "Part processed successfully",
  "process_detail_id": "uuid..."
}
```

**`PUT /api/v1/process/inspect`**
* **Actor:** Inspector
* **Description:** Updates the `inspection_status` of an existing process detail row.
* **Request Payload:**
```json
{
  "qr_id": "QR-SH-001",
  "inspection_status": "REJECTED", 
  "reject_reason": "Deep scratch on left side" 
}
```
* *Note: `reject_reason` is strictly required if status is `REJECTED` or `REWORK`.*

### 3.3 Assembly Process APIs
These endpoints handle the validation and execution of the digital BOM (Bill of Materials) linking.

**`POST /api/v1/assembly/validate-components`**
* **Actor:** Linker
* **Description:** A pre-check to verify the scanned parts are valid before final commit.
* **Request Payload:**
```json
{
  "target_quantity": 6,
  "scanned_components": [
    "QR-SH-001",
    "QR-VS-045",
    "QR-BT-088"
  ]
}
```
* **Backend Logic:**
  1. Check if all `qr_ids` have `overall_status = COMPLETED`.
  2. Determine the `part_group` for each QR.
  3. Ensure all groups are distinct (no duplicate groups).
* **Response (200 OK):**
```json
{
  "is_valid": true,
  "missing_groups": ["Cushion", "Liner", "Hardware"],
  "message": "3 components validated. 3 remaining."
}
```

**`POST /api/v1/assembly/commit`**
* **Actor:** Linker
* **Description:** Finalizes the assembly, creating `ASSEMBLY_PROCESS_DETAIL` and `ASSEMBLY_MAPPING`.
* **Request Payload:**
```json
{
  "parent_qr_id": "QR-HLMT-999",
  "assemble_line_id": "770e8400-e29b-41d4-a716-446655441111",
  "scanned_components": [
    { "qr_id": "QR-SH-001", "part_group": "Shell" },
    { "qr_id": "QR-VS-045", "part_group": "Visor" },
    { "qr_id": "QR-BT-088", "part_group": "Belt" },
    { "qr_id": "QR-CU-012", "part_group": "Cushion" },
    { "qr_id": "QR-LN-005", "part_group": "Liner" },
    { "qr_id": "QR-HW-002", "part_group": "Hardware" }
  ]
}
```
* **Backend Logic:** Wraps the creation of 1 Assembly Detail row and 6 Assembly Mapping rows in an atomic database transaction.

### 3.4 Admin & Master APIs
**`POST /api/v1/jobcards/generate`**
* **Actor:** Admin
* **Description:** Creates the Job Card and initiates the bulk generation of QR codes.
* **Request Payload:**
```json
{
  "jobcard_no": "JC-SH-2026-01",
  "part_model": "uniqueid6",
  "part_composition": "ABS Plastic",
  "quantity": 10
}
```
* **Backend Logic:** Uses a bulk insert (e.g., Django's `bulk_create`) to generate 10 rows in `QR_MASTER` efficiently, rather than a loop of individual inserts.

### 3.5 New Self-Service & Traceability APIs
**`GET /users/me`**
* **Description:** Retrieves the current user's profile based on the JWT token.
* **Benefit:** Allows mobile apps to display worker name and assigned station without hardcoding IDs.

**`GET /scan/my-history`**
* **Description:** Retrieves all production events (scans/links) logged by the current user.

**`GET /scan/user-history/{user_id}`**
* **Description:** Allows Admins to monitor the output of a specific sub-user.

---

## 4. Error Handling Protocol

All APIs must return standardized error formats to ensure the mobile app UI can display helpful messages to the operators on the floor.

**Standard Error Response Structure (400 / 403 / 404 / 500):**
```json
{
  "error_code": "ERR_DUPLICATE_GROUP",
  "message": "Assembly validation failed. Two distinct Visor components were scanned.",
  "details": {
    "conflicting_qrs": ["QR-VS-045", "QR-VS-089"]
  }
}
```

**Common Error Codes to Implement:**
* `ERR_QR_LOCKED`: Part is marked SCRAPPED/REJECTED.
* `ERR_STAGE_SKIP`: Previous stage is missing or not marked OK.
* `ERR_INVALID_SHIFT`: Operator session has expired.
* `ERR_DUPLICATE_GROUP`: Linker scanned two of the same component type.
* `ERR_COMPONENT_NOT_READY`: Linker scanned a component that hasn't finished processing.
```