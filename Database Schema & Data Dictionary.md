# Database Schema & Data Dictionary

## 1. Overview
The database architecture for the Traceability Platform is designed for infinite vertical and horizontal scaling. By heavily normalizing the data and avoiding monolithic "wide" tables with hardcoded columns, the system can support $n$ number of unique manufacturing processes, machines, and component assemblies without requiring database migrations.

---

## 2. Core Design Principles
* **QR-Centric Architecture:** The `qr_id` acts as the definitive source of truth. Every physical item's lifecycle revolves around this primary identifier.
* **Event-Sourced Process Logging:** Instead of updating status columns on a single `PRODUCT` row, the system appends new rows to `SCANNER_PROCESS_DETAIL` and `ASSEMBLY_PROCESS_DETAIL`. This preserves a perfect, immutable historical audit trail.
* **Dynamic Assembly Mapping:** Hardcoded component lists (e.g., shell, visor, belt) are replaced by the `ASSEMBLY_MAPPING` table, allowing the Linker to dynamically map distinct parts to a parent product.

---

## 3. Data Dictionary

### 3.1 Master Data Tables
These tables define the physical environment and the personnel operating within the facility.

**`USER`**
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Primary Key | Unique identifier for the user. |
| `role` | String | Not Null | Defines permissions (`Super Admin`, `Admin`, `Scanner`, `Linker`, `Inspector`). |
| `shift` | String | Nullable | Current active shift timing (e.g., `09:00-17:00`). |

**`STATION`**
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `station_id` | String | Primary Key | Unique internal ID. |
| `name` | String | Not Null | Name of the station. |
| `process` | String | Not Null | E.g., `Moulding`, `Final Assembly`. |
| `active` | Boolean | Not Null | Whether the station is currently operational. |

### 3.2 Core Order Entities
These tables manage the genesis of products on the floor.

**`JOB_CARD`**
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Primary Key | Unique internal ID. |
| `jobcard_no` | String | Unique Key | Human-readable Job Card number (e.g., `JC-SH-2026`). |
| `part_model` | String | Not Null | Identifier for the master part defined by the Super Admin. |
| `quantity` | Integer | Not Null | Target production quantity. |
| `status` | String | Not Null | `CREATED`, `IN PROGRESS`, `COMPLETED`. |
| `created_by` | UUID | Foreign Key | Links to `USER.id` (Admin who created it). |

**`QR_MASTER`**
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Primary Key | Unique internal ID. |
| `qr_id` | String | Unique Key | The actual string printed on the QR label. |
| `jobcard_id` | UUID | Foreign Key | Links back to the batch `JOB_CARD.id`. |
| `status` | String | Not Null | `UNUSED`, `IN USE`, `COMPLETED`, `SCRAPPED`. |

**`PRODUCT`**
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Primary Key | Unique internal ID. |
| `qr_id` | String | FK, Unique | Links to `QR_MASTER`. The anchor for a physical item. |
| `overall_status` | String | Not Null | Macro status: `WIP`, `COMPLETED`, `SCRAPPED`. |

### 3.3 Dynamic Process Detail Tables
These tables replace traditional `SCAN_LOG` and `INSPECTION` tables, merging them into unified event records.

**`SCANNER_PROCESS_DETAIL`**
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Primary Key | Unique internal ID for this specific stage event. |
| `qr_id` | String | Foreign Key | The part being processed. |
| `process_name` | String | Not Null | Inherited from the Machine (e.g., `Polishing`). |
| `station_id` | String | Foreign Key | The workstation used. |
| `scanner_id` | UUID | Foreign Key | The user who did the processing. |
| `inspector_id` | UUID | Foreign Key | Nullable until explicitly inspected. |
| `inspection_status`| String | Not Null | `PENDING`, `OK`, `REWORK`, `REJECTED`. |
| `reject_reason` | String | Nullable | Mandatory if status is `REWORK` or `REJECTED`. |
| `start_time` | Timestamp| Not Null | When the scan occurred. |
| `end_time` | Timestamp| Nullable | When the stage is fully cleared. |

**`ASSEMBLY_PROCESS_DETAIL`**
*Structure is identical to `SCANNER_PROCESS_DETAIL`, but links to `station_id` and `linker_id` instead.*

### 3.4 Dynamic Assembly Mapping
This table handles the digital "glue" that binds sub-components into a parent product.

**`ASSEMBLY_MAPPING`**
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Primary Key | Unique internal ID. |
| `assembly_process_id`| UUID | Foreign Key | Links to `ASSEMBLY_PROCESS_DETAIL.id`. |
| `child_qr_id` | String | Foreign Key | The specific `qr_id` of the consumed component. |
| `part_group` | String | Not Null | Group identifier (e.g., `Visor`, `Shell`) used to validate distinct part constraints before committing the assembly. |

---

## 4. Entity-Relationship Diagram

```mermaid
erDiagram
    %% User & Master Entities
    USER {
        uuid id PK
        string role "Super Admin, Admin, Scanner, Linker, Inspector"
        string shift "e.g., 09:00-17:00"
    }
    
    STATION {
        uuid station_id PK
        string name
        string process
        bool active
    }

    %% Core Entities
    JOB_CARD {
        uuid id PK
        string jobcard_no UK
        date jobcard_date
        string part_model
        string part_composition
        int quantity
        string status "CREATED, IN PROGRESS, COMPLETED"
        uuid created_by FK
        timestamp created_at
    }

    QR_MASTER {
        uuid id PK
        string qr_id UK
        uuid jobcard_id FK
        string serial_no
        string status "UNUSED, IN USE, COMPLETED, SCRAPPED"
        timestamp created_at
    }

    PRODUCT {
        uuid id PK
        string qr_id FK "Unique Key"
        string overall_status "WIP, COMPLETED, SCRAPPED"
        timestamp created_at
    }

    %% N-Number Process Detail Tables
    SCANNER_PROCESS_DETAIL {
        uuid id PK
        string qr_id FK
        string process_name "e.g., Moulding, Polish"
        uuid station_id FK
        uuid scanner_id FK
        uuid inspector_id FK "Nullable until inspected"
        string inspection_status "PENDING, OK, REWORK, REJECTED"
        string reject_reason
        timestamp start_time
        timestamp end_time
    }

    ASSEMBLY_PROCESS_DETAIL {
        uuid id PK
        string parent_qr_id FK
        string process_name "e.g., Final Assembly"
        uuid station_id FK
        uuid linker_id FK
        uuid inspector_id FK "Nullable until inspected"
        string inspection_status "PENDING, OK, REWORK, REJECTED"
        string reject_reason
        timestamp start_time
        timestamp end_time
    }

    %% Dynamic Component Interlinking
    ASSEMBLY_MAPPING {
        uuid id PK
        uuid assembly_process_id FK
        string child_qr_id FK "The scanned component"
        string part_group "e.g., Shell, Visor, Belt"
    }

    %% Relationships
    USER ||--o{ JOB_CARD : "creates"
    JOB_CARD ||--|{ QR_MASTER : "generates QR"
    QR_MASTER ||--o| PRODUCT : "initializes"
    
    %% Station Links
    PRODUCT ||--o{ SCANNER_PROCESS_DETAIL : "undergoes"
    STATION ||--o{ SCANNER_PROCESS_DETAIL : "hosts"
    
    %% Assembly Process Links
    PRODUCT ||--o{ ASSEMBLY_PROCESS_DETAIL : "undergoes"
    STATION ||--o{ ASSEMBLY_PROCESS_DETAIL : "hosts"
    USER ||--o{ ASSEMBLY_PROCESS_DETAIL : "links and inspects"
    
    %% Dynamic Mapping Links
    ASSEMBLY_PROCESS_DETAIL ||--|{ ASSEMBLY_MAPPING : "contains"
    QR_MASTER ||--o{ ASSEMBLY_MAPPING : "used as component"