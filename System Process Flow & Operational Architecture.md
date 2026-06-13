# System Process Flow & Operational Architecture

## 1. Overview
This document outlines the definitive operational blueprint for the QR-based Product Traceability System. It details the step-by-step physical workflow on the manufacturing floor and how those actions translate into backend state changes. The architecture is designed to enforce zero process skipping, ensure complete traceability, and support infinite dynamic scaling across $n$ number of workstations.

---

## 2. Phase 1: Global Configuration & Job Initiation
Before any scanning occurs on the floor, the system must be configured and provisioned by the administrative tiers.

### 2.1 Super Admin Setup
* **Part Defining:** The Super Admin defines the master catalog of parts (e.g., Shell, Visor, Belt) that the facility manufactures.
* **Admin Provisioning:** Creates the Admin (Master) accounts and assigns them oversight over specific parts or facility sectors.

### 2.2 Admin (Master) Configuration
* **Environment Mapping:** The Admin defines the physical and operational constraints of the factory:
  * **Shifts:** Configures time blocks (e.g., "Morning 09:00-17:00").
  * **Machines:** Registers individual physical workstations and generates a static `Machine QR` for each.
  * **Assemble Lines:** Registers assembly stations and generates a static `Assemble Line QR` for each.
* **User Onboarding:** The Admin creates Sub-User profiles and rigidly assigns them to one of three roles: `Scanner`, `Linker`, or `Inspector`.
* **Job Card Generation:** To start production, the Admin creates a Job Card (specifying the part model, composition, and quantity). The system automatically generates a batch of unique QR codes (QR IDs) mapped to this Job Card, which are printed and attached to the raw materials.

---

## 3. Phase 2: The Scanner Process (Component Processing)
This process applies to individual components moving through single-machine stages (e.g., Moulding, Polishing, Painting). 

### 3.1 Shift Initialization (The "Login")
* **Action:** At the start of a shift, the `Scanner` sub-user opens their mobile app and scans the static `Machine QR` physically attached to their workstation.
* **System State:** The backend maps the `Scanner`'s user ID, the `Machine ID`, and the current `Shift` into a temporary active session. The mobile app UI unlocks the "Scan Parts" interface.

### 3.2 Continuous Processing Loop
* **Action:** The operator completes their physical work on a part and scans the part's unique `QR ID`. 
* **System State:** The backend creates a new row in the `SCANNER_PROCESS_DETAIL` table, permanently logging the exact time, user, and machine associated with that specific QR for this specific stage.
* **UI Feedback:** The app flashes green (Success) and immediately resets the camera to scan the next part. 

### 3.3 Smart Inspection Filter
To maintain high velocity, the Inspector does not scan every single approved part.
* **Scenario A: Initial Pass (Implicit OK):** If the part visually passes inspection, the Inspector does nothing. The system assumes an implicit `OK` because the part successfully moves to the next downstream process.
* **Scenario B: Issue Found (Explicit Scan):** If the part is defective, the `Inspector` opens their app, scans the part's `QR ID`, and selects either `REJECTED` or `REWORK`. 
  * If `REJECTED`: The backend marks the QR as scrapped. The QR is permanently locked and cannot be scanned anywhere else.
  * If `REWORK`: The backend updates the part's status to `REWORK` and flags it.
* **Scenario C: Rework Loop:** The physical part is handed back to the `Scanner`. The Scanner re-processes it and scans the QR again. The Inspector *must* now explicitly scan this reworked part to clear the flag and mark it `OK` before it can leave the station.

---

## 4. Phase 3: The Assembly Process (Component Interlinking)
This process occurs when multiple distinct components are brought together to form a parent product (e.g., Final Helmet Assembly).

### 4.1 Shift Initialization
* **Action:** The `Linker` sub-user opens their app and scans the static `Assemble Line QR`.
* **System State:** The backend maps the Linker, Assemble Line, and Shift to an active session.

### 4.2 Assembly Configuration & Validation
* **Action:** The Linker manually inputs the target number of components required for the assembly (e.g., $n=6$).
* **Action:** The Linker scans the `QR ID` of the 6 distinct parts.
* **Backend Validation Check:** The system verifies two critical conditions before allowing the assembly to proceed:
  1. All scanned components must have a completed status from their previous individual scanner processes.
  2. The components must be distinct by `part_group`. (e.g., The system throws an error if the Linker accidentally scans two Visors instead of one Visor and one Belt).

### 4.3 Interlinking & Completion
* **System State:** Once validated, the system generates a new `parent_qr_id` for the final assembly (or assigns an existing one if pre-printed). It writes a record to `ASSEMBLY_PROCESS_DETAIL` and inserts $n$ rows into `ASSEMBLY_MAPPING`, permanently linking the component QRs to the parent QR.
* **Inspection:** The exact same Smart Inspection logic (Implicit OK vs. Explicit Reject/Rework) applies to the final assembled product.

---

## 5. Visual Flow Diagram

```mermaid
graph TD
    %% Main Admin Flow & Master
    Start([Start]) --> SuperAdmin[Super Admin] --> PartDefining[[Part Defining]]
    PartDefining --> AdminCreation[Admin Creation] --> AssignPart[Assign Part] --> PartAdmin["Part Admin(s)"]
    PartAdmin --> Master

    subgraph Master
        master[Master] --> define_shift["Define Shift"]
        master --> define_machine["Define Machines"]
        master --> define_assemble["Define Assemble Line"]
        master --> sub_user["Onboard Sub Users"]
        
        %% Explicit Role Definitions in Master
        sub_user --> def_scanner["Role: Scanner"]
        sub_user --> def_linker["Role: Linker"]
        sub_user --> def_inspector["Role: Inspector"]
    end

    %% Job Card and QR
    PartAdmin --> JobcardCreation["Job Card Creation"] --> ModelDetail["Model Details"] --> QRGen["QR Code Generation"] --> QR["Shared QR Code"]
    
    %% Main Connections
    PartAdmin --> ScannerProcess1_sub
    PartAdmin --> ScannerProcessN["Scanner Process 2 ... n"]
    PartAdmin --> AssembleProcess1_sub
    PartAdmin --> AssembleProcessN["Assemble Process 2 ... n"]

    %% Detailed Scanner Process 1 
    subgraph ScannerProcess1_sub ["Scanner Process 1 (Detailed)"]
        P1_Scanner["Scanner (Sub-user)"] -- "1. Scans once per shift" --> P1_MachineQR["Machine QR"]
        P1_MachineQR --> P1_ProfileMap["Maps Machine & Shift to Profile"]
        
        P1_ProfileMap -- "2. Starts working" --> P1_ScanPart["Scan Part QRs (Loop)"]
        P1_ScanPart -. "Saves User, Shift & Machine data" .-> QR
        
        P1_ScanPart --> P1_Inspector["Inspector (Sub-user)"] --> P1_InspectorCheck{"Inspector Checks Part"}
        
        P1_InspectorCheck -- "Initial OK (No Scan)" --> P1_Completed["Done (Scanner Process 1)"]
        P1_InspectorCheck -- "Found Issue (Scans QR)" --> P1_MarkStatus{"Mark QR Status"}
        P1_InspectorCheck -- "Reviewing Rework (Scans QR)" --> P1_MarkStatus
        
        P1_MarkStatus -- "Reject" --> P1_Reject["Update QR: Rejected"] -.-> QR
        P1_MarkStatus -- "Rework" --> P1_Rework["Update QR: Rework"] -.-> QR
        P1_MarkStatus -- "OK (Rework Fixed)" --> P1_ReworkOK["Update QR: OK"] -.-> QR
        
        P1_Rework --> P1_ScanPart
        P1_ReworkOK --> P1_Completed
    end

    %% Detailed Assembly Process 1 
    subgraph AssembleProcess1_sub ["Assembly Process 1 (Detailed)"]
        A_Linker["Linker (Sub-user)"] -- "1. Scans once per shift" --> A_AssembleQR["Assemble Line QR"]
        A_AssembleQR --> A_ProfileMap["Maps Assemble Line & Shift to Profile"]
        
        A_ProfileMap -- "2. Starts working" --> A_ManualInput["Manual Input: Number of Parts (e.g., n=6)"]
        A_ManualInput --> A_ScanParts["Scan 'n' Distinct Part QRs"]
        
        A_ScanParts --> A_Validation{"Validation: Are parts distinct by group?"}
        A_Validation -- "No (Invalid / Duplicate)" --> A_ScanParts
        A_Validation -- "Yes (Valid)" --> A_Interlink["Interlink Parts (Assembly Complete)"]
        A_Interlink -. "Saves Interlink Data" .-> QR
        
        A_Interlink --> A_Inspector["Inspector (Sub-user)"] --> A_InspectorCheck{"Inspector Checks Assembly"}
        
        A_InspectorCheck -- "Initial OK (No Scan)" --> A_Completed["Done (Assembly 1)"]
        A_InspectorCheck -- "Found Issue (Scans QR)" --> A_MarkStatus{"Mark QR Status"}
        A_InspectorCheck -- "Reviewing Rework (Scans QR)" --> A_MarkStatus
        
        A_MarkStatus -- "Reject" --> A_Reject["Update QR: Rejected"] -.-> QR
        A_MarkStatus -- "Rework" --> A_Rework["Update QR: Rework"] -.-> QR
        A_MarkStatus -- "OK (Rework Fixed)" --> A_ReworkOK["Update QR: OK"] -.-> QR
        
        A_Rework --> A_ManualInput
        A_ReworkOK --> A_Completed
    end

    %% MAPPINGS FROM MASTER TO FLOOR EXECUTION
    def_scanner -. "Assigns to" .-> P1_Scanner
    def_scanner -. "Assigns to" .-> ScannerProcessN
    def_linker -. "Assigns to" .-> A_Linker
    def_linker -. "Assigns to" .-> AssembleProcessN
    def_inspector -. "Assigns to" .-> P1_Inspector
    def_inspector -. "Assigns to" .-> A_Inspector
    def_inspector -. "Assigns to" .-> ScannerProcessN
    def_inspector -. "Assigns to" .-> AssembleProcessN

    define_machine -. "Configures" .-> P1_MachineQR
    define_machine -. "Configures" .-> ScannerProcessN
    define_assemble -. "Configures" .-> A_AssembleQR
    define_assemble -. "Configures" .-> AssembleProcessN

    define_shift -. "Applies to" .-> P1_ProfileMap
    define_shift -. "Applies to" .-> A_ProfileMap
    define_shift -. "Applies to" .-> ScannerProcessN
    define_shift -. "Applies to" .-> AssembleProcessN

    %% DYNAMIC ROUTING LOGIC
    P1_Completed --> RouteDecision{Next Stage?}
    RouteDecision -- "Next Scanner" --> ScannerProcessN
    RouteDecision -- "To Assembly" --> AssembleProcess1_sub
    ScannerProcessN --> RouteDecisionN{Next Stage?}
    RouteDecisionN -- "Next Scanner" --> ScannerProcessN
    RouteDecisionN -- "To Assembly" --> AssembleProcess1_sub

    A_Completed --> RouteDecisionA{Next Stage?}
    RouteDecisionA -- "Next Assembly" --> AssembleProcessN
    RouteDecisionA -- "Finish" --> FinalComplete([Final Completion])
    AssembleProcessN --> RouteDecisionAN{Next Stage?}
    RouteDecisionAN -- "Next Assembly" --> AssembleProcessN
    RouteDecisionAN -- "Finish" --> FinalComplete