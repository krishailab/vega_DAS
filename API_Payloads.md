# Vega Traceability Backend - API & Status Documentation

## 1. System Data & Status Dictionary
Throughout the Vega Traceability system, there are several strict "Status" and "Role" strings that dictate operational logic and security.

### User `role` (Authorization Strings)
* **`Super Admin`**: Platform owner. Can create Master Admins and Part Groups.
* **`Master Admin`**: Organization owner. Can create Sub-Users, Machines, Shifts, and Job Cards.
* **`Scanner`**: Sub-User. Performs single-process high-speed barcode scans.
* **`Linker`**: Sub-User. Performs complex multi-component assembly linkages.
* **`Inspector`**: Sub-User. Intercepts and resolves `PENDING` items (marks them OKAY, REWORKED, or REJECTED).

### Product `overall_status`
* **`UNUSED`**: The QR code has been generated but has never been scanned on the production floor.
* **`WIP`**: (Work In Progress) The QR code has been scanned at least once and is currently moving through the assembly line.
* **`SCRAPPED`**: The product was critically rejected by an Inspector and is permanently locked out of the system.
* **`FINISHED`**: The product has completed all required assembly and scanning processes.

### Scan/Link `inspection_status`
* **`OKAY`**: The default status for any scan or link. Represents a successfully completed process that does not require an Inspector.
* **`PENDING`**: A process that requires manual verification from an Inspector (triggered automatically if the part was previously marked `REWORKED` for this specific process).
* **`REWORKED`**: Set manually by an Inspector if the part failed but can be fixed. Forces the next scan of this part to default to `PENDING`.
* **`REJECTED`**: Set manually by an Inspector if the part is unfixable. Automatically changes the `overall_status` to `SCRAPPED` globally.

### Job Card & QR `status`
* **`CREATED`**: Job card is created but not active.
* **`ACTIVE`**: Job card is currently active on the floor.
* **`COMPLETED`**: Job card has fulfilled its required quantity.
* **`IN USE`**: A `QR_MASTER` record that has successfully initialized into a `PRODUCT`.

---

## 2. Role-Based API Payloads

### A. Super Admin APIs
Super Admins manage the platform and onboard Master Admins (Organizations).

**1. Master Admin Management**
* **Create**: `POST /users/`
  ```json
  {
    "first_name": "John",
    "last_name": "Doe",
    "age": 35,
    "gender": "M",
    "blood_group": "O+",
    "employee_id": "VEGA1001",
    "mobile_number": "9876543210",
    "role": "Master Admin",
    "email": "master.admin@vega.com",
    "password": "securepassword123",
    "part_id": "PTR26AA0001" 
  }
  ```
* **Get All Users**: `GET /users/` (Can view all system users)
* **Get User**: `GET /users/{user_id}`
* **Update Master Admin**: `PUT /users/{user_id}`
* **Delete Master Admin**: `DELETE /users/{user_id}`
* **View User History**: `GET /scan/user-history/{user_id}`

**2. Part Group Management**
* **Create Part**: `POST /api/create-part/`
  ```json
  {
    "name": "Front Bumper Assembly",
    "type": "Body Component",
    "active": true
  }
  ```
* **Get All Parts**: `GET /api/create-part/`
* **Get Part**: `GET /api/create-part/{part_id}`
* **Update Part**: `PUT /api/create-part/{part_id}`
* **Delete Part**: `DELETE /api/create-part/{part_id}`

---

### B. Master Admin APIs
Master Admins manage their specific manufacturing floor, job cards, and sub-users.

**1. Sub-User Management (Scanner, Linker, Inspector)**
* **Create Sub-User**: `POST /users/`
  ```json
  {
    "first_name": "Jane",
    "last_name": "Smith",
    "age": 28,
    "gender": "F",
    "blood_group": "A+",
    "employee_id": "VEGA2005",
    "mobile_number": "9123456780",
    "role": "Scanner",
    "password": "scannerpass123"
  }
  ```
* **Get Users**: `GET /users/?role=Scanner` (Filters by role available)
* **Update User**: `PUT /users/{user_id}`
* **Delete User**: `DELETE /users/{user_id}`
* **View Sub-User History**: `GET /scan/user-history/{user_id}`

**2. Station Management**
* **Create Station**: `POST /stations/`
  ```json
  {
    "name": "MC-CNC-001",
    "process": "Milling",
    "active": true
  }
  ```
* **Get All Stations**: `GET /stations/`
* **Update Station**: `PUT /stations/{station_id}`
* **Delete Station**: `DELETE /stations/{station_id}`
* **Download Station QR PDF**: `GET /stations/{station_id}/download-pdf`

**4. Shift Management**
* **Create Shift**: `POST /shifts/`
  ```json
  {
    "name": "Morning Shift",
    "start_time": "08:00:00",
    "end_time": "16:00:00",
    "active": true
  }
  ```
* **Get All Shifts**: `GET /shifts/`
* **Update Shift**: `PUT /shifts/{shift_id}`
* **Delete Shift**: `DELETE /shifts/{shift_id}`

**5. Job Card Management**
* **Create Job Card**: `POST /job-cards/`
  ```json
  {
    "jobcard_no": "JC-SH-2026",
    "jobcard_date": "2026-04-26",
    "part_composition": "Polycarbonate",
    "quantity": 500
  }
  ```
* **Get All Job Cards**: `GET /job-cards/`
* **Delete Job Card**: `DELETE /job-cards/{jobcard_id}`
* **Download Job Card QRs**: `GET /job-cards/{jobcard_id}/download-qrs` (Downloads `.xlsx` file)
* **Generate Reverse Sequence XLSX**: `POST /job-cards/reverse-import/generate-sequence`
  ```json
  {
    "start_id": "XXXXXXXXXXXX679",
    "quantity": 10
  }
  ```
  > **Note**: Generates an `.xlsx` file with a sequence of IDs starting from `start_id`.

**6. Analytics & Monitoring**
* **Get Dashboard Summary**: `GET /scan/dashboard-summary`
  ```json
  {
    "WIP": 45,
    "FINISHED": 120,
    "SCRAPPED": 5,
    "total": 170
  }
  ```
  > **Note**: Provides real-time macro status counts for the Master Admin.

---

### C. Scanner APIs
Scanners perform high-speed single-process processing.

**1. Station Assignment (Clock-in)**
**Path**: `POST /users/assign-station`
```json
{
  "station_id": "STN26AA0001",
  "timestamp": "2026-04-26T08:05:00"
}
```

**2. Scan Part**
**Path**: `POST /scan/`
```json
{
  "qr_id": "PRD26AA0001"
}
```
> **Note**: Automatically inherits the `process_name` from the assigned Station! Defaults to `OKAY`.

---

### D. Linker APIs
Linkers bind multiple component QRs into a Parent QR.

**1. Station Assignment (Clock-in)**
**Path**: `POST /users/assign-station`
```json
{
  "station_id": "STN26AA0001",
  "timestamp": "2026-04-26T08:05:00"
}
```

* **Option 1 (via ID)**: `PUT /users/{user_id}/linker-capacity`
* **Option 2 (Self)**: `PUT /users/me/linker-capacity`
  ```json
  {
    "capacity": 3
  }
  ```

**3. Link Parts (Assembly Start)**
**Path**: `POST /scan/link`
```json
{
  "qr_ids": ["PRD26AA0001", "PRD26AA0002", "PRD26AA0003", "PRD26AA0004"]
}
```
> **Note**: Backend enforces array length matches capacity, and ensures all parts are distinct models. **Linking updates the status of all components to WIP as a single unit**.

---

### E. Inspector APIs
Inspectors intercept `PENDING` scans and resolve them.

**1. Station Assignment (Clock-in)**
**Path**: `POST /users/assign-station`
```json
{
  "station_id": "STN26AA0001",
  "timestamp": "2026-04-26T08:05:00"
}
```

**2. Inspect Part (Resolve Pending)**
**Path**: `PUT /scan/inspect`
**Content-Type**: `multipart/form-data`
**Form Data Fields**:
* `qr_id`: `PRD26AA0001`
* `inspection_status`: `REWORKED` or `REJECTED` or `OKAY`
* `reject_reason` (Optional): `Scratch on surface`
* `image` (File/Optional): `[Physical Image File]`
> **Note**: Image is **strictly mandatory** if `inspection_status` is `REJECTED`.


---

### F. Any Authenticated User APIs

**1. Update My Profile**
**Path**: `PUT /users/{user_id}`
```json
{
  "first_name": "Jane",
  "last_name": "Smith",
  "password": "newpassword123"
}
```

**2. View My Profile (Self)**
**Path**: `GET /users/me`
> **Note**: Returns full profile details without needing a `user_id`.

**3. View My Activity History (Self)**
**Path**: `GET /scan/my-history`
> **Note**: Returns a list of all scans, links, and inspections performed by the current user.

---

### G. Public APIs

**1. Get Full Product Traceability History**
**Path**: `GET /scan/history/{qr_id}`
```json
{
  "product": {
    "qr_id": "PRD26AA0001",
    "overall_status": "WIP",
    "created_at": "2026-04-25T21:40:00"
  },
  "history": [
    {
      "scan_id": "SCN26AA0001",
      "qr_id": "PRD26AA0001",
      "process_name": "Moulding",
      "inspection_status": "OKAY",
      "type": "Scanner Process"
    },
    {
      "assembly_id": "ASM26AA0001",
      "qr_ids": ["PRD26AA0001", "PRD26AA0002"],
      "process_name": "Final Assembly",
      "type": "Assembly Process",
      "linked_components": [
        {
          "part_group": "Visor",
          "product": {
            "overall_status": "WIP"
          },
          "history": [ ... nested tree ... ]
        }
      ]
    }
  ]
}
```

---

### H. Asset Management APIs (Master Admin Only)
Manage site equipment, vehicles, and tools.

**1. Category Management**
* **Create Category**: `POST /assets/categories`
  ```json
  { "name": "IT Equipment" }
  ```
* **Get All Categories**: `GET /assets/categories`

**2. Asset CRUD**
* **Create Asset**: `POST /assets/` (Multipart Form Data)
  * `name`: `MacBook Pro`
  * `asset_no`: `VEGA-IT-001`
  * `model`: `M2 Max`
  * `brand`: `Apple`
  * `purchase_date`: `2024-05-10`
  * `cost`: `250000`
  * `category_id`: `CAT26AA0001`
  * `is_warranty`: `true`
  * `warranty_expiry_date`: `2026-05-10`
  * `invoice_pdf`: `[File]`
  * `images`: `[Files]`
* **Get All Assets**: `GET /assets/` (Filters: `category_id`, `brand`, `search`, etc.)

**3. Asset Assignment & Submission**
* **Assign Asset**: `POST /assets/{asset_id}/assign`
  * `user_id`: `USR26AA0005`
  * `notes`: `Issued for project X`
* **Submit/Return Asset**: `POST /assets/{asset_id}/submit`
  * `status`: `RECEIVED` (or `RETURNED`)
  * `condition`: `Good`
  * `remarks`: `Returned with original box`

**4. Asset Dashboard**
* **Get Asset Dashboard**: `GET /assets/dashboard`
  ```json
  {
    "status_summary": { "total": 50, "assigned": 20, "available": 30 },
    "category_summary": [ { "category_id": "...", "category_name": "...", "count": 10 } ],
    "warranty_summary": { "under_warranty": 15, "under_guarantee": 5, "no_warranty": 30 },
    "recent_submissions": [ ... list of 5 latest ... ]
  }
  ```
