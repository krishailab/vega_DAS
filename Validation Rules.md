# Core Business Logic & Validation Rules

## 1. Overview
This document defines the strict backend validation rules for the Traceability Platform. [cite_start]The backend APIs must enforce these rules at the database level to maintain absolute data integrity, prevent operator errors on the floor, and ensure zero process skipping[cite: 249]. 

---

## 2. Shift & Session Rules (Authentication)
Before an operator can log a production event, the system must validate their physical and temporal context.

* **Mandatory Mapping:** A `Scanner` or `Linker` cannot scan a part until an active `machine_id` or `assemble_line_id` is mapped to their session via an initial Shift Scan.
* **Role Isolation:** * A user with the `Scanner` role cannot log into an `Assemble Line QR`.
  * A user with the `Linker` role cannot log into a `Machine QR`.
  * A user with the `Inspector` role does not map to a machine; their permissions are global across the stages they oversee.

---

## 3. Data Visibility & Access Rules (RBAC)
To protect organizational data, history and profile visibility are restricted.

* **Profile Access:**
  * Users can access their own profile via `/users/me`.
  * Admins can access sub-user profiles via `/users/{user_id}` only if the sub-user belongs to their organization.
* **History Visibility:**
  * **Self:** All users can view their own activity history via `/scan/my-history`.
  * **Master Admin:** Can view history of any sub-user (`Scanner`, `Linker`, `Inspector`) within their specific organization.
  * **Super Admin:** Global visibility across all organizations.
  * **Access Denied:** Any attempt by a sub-user to view another user's history via `/scan/user-history/{user_id}` must return a `403 Forbidden` error.

---

## 3. QR Lifecycle & State Machine Rules
The `qr_id` acts as a state machine. The backend must validate the current state of a QR before allowing any new action.

* [cite_start]**Duplicate Protection:** Duplicate QR usage is strictly blocked[cite: 226]. The system must reject a scan if the `qr_id` is already logged as active in the exact same process (unless it is returning from a `REWORK` state).
* [cite_start]**Stage Progression Lock:** Stage skipping is blocked[cite: 227]. [cite_start]The next stage is blocked unless the previous inspection is marked `APPROVED` (or `OK`)[cite: 147, 148, 149].
* [cite_start]**Scrap / Lockout:** If an inspector marks a part as `REJECTED`, the system must route it to scrap[cite: 177]. The `overall_status` in the `PRODUCT` table becomes `SCRAPPED`. Any future attempt to scan this QR ID at any workstation must return a hard error.

---

## 4. Smart Inspection & Rework Logic
To optimize floor speed, the inspection process relies on a mix of implicit and explicit validations.

* **Implicit Approval (Speed Mode):** If a part completes a scanner process and is subsequently scanned at the *next* downstream stage without any Inspector intervention, the backend implicitly assumes the previous stage's `inspection_status` is `OK`.
* [cite_start]**Explicit Rejection/Rework:** If an inspector explicitly scans a part, they must choose `REWORK` or `REJECTED`[cite: 176]. [cite_start]If either is selected, a `reject_reason` payload is strictly mandatory[cite: 198]. 
* **The Rework Loop Enforcement:** * If a part is marked `REWORK`, it cannot move to the next downstream stage. It must be routed back to rework[cite: 177].
  * The `Scanner` must scan it again (creating a new `start_time` and `end_time` in `SCANNER_PROCESS_DETAIL`).
  * **Crucial:** Once reworked, the Implicit Approval rule is suspended. The Inspector *must* explicitly scan the part again to mark it `OK` before it can progress.

---

## 5. Assembly Validation Rules (BOM Integrity)
The assembly stage is the most complex validation gate. It digitally binds multiple `child_qr_id` components to a `parent_qr_id`.

* [cite_start]**Component Prerequisite:** Assembly without approved components is blocked[cite: 228]. Every `child_qr_id` submitted for assembly must currently have an `overall_status` of `COMPLETED` from its upstream scanner processes.
* [cite_start]**Distinct Group Validation:** Prevent duplicate components[cite: 180]. If the Linker inputs that $n=6$ parts are required, the backend must verify the array of scanned components contains exactly one item from each required `part_group` (e.g., 1 Shell, 1 Visor, 1 Belt). If the array contains two QRs from the "Visor" group, the API must reject the payload.
* [cite_start]**BOM Completeness:** Validate BOM (all components required)[cite: 179]. The assembly cannot be committed unless the number of scanned, valid parts exactly matches the Linker's target input.
* **Parent Generation:** The `parent_qr_id` can only be generated (or activated) after the `ASSEMBLY_MAPPING` validations successfully pass.

---

## 6. Edge Cases & Failsafes
* **Orphaned Sessions:** If a shift ends (e.g., 17:00 is reached) and a part is left `PENDING` (scanned but not completed/inspected), the backend should flag the row in `PROCESS_DETAIL` as `INCOMPLETE`. 
* **Database Transactions:** When an assembly is completed, the backend must use a SQL Transaction to write to `ASSEMBLY_PROCESS_DETAIL` and `ASSEMBLY_MAPPING` simultaneously. If one fails, the entire action must rollback to prevent orphaned mapping links.