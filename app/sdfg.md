# Part ID (`part_id`) Validation Rules

The `part_id` is a primary foreign key used to scope access and normalize operations across Users (Admins/Operators), Stations, Parts, and Job Cards.

---

## 1. User & Profile Management (`user_api.py`)

* **Role Constraint (Creation & Verification):**
  * Any user with the role `"Master Admin"` **must** be assigned a `part_id`. If `part_id` is missing during create or update, it raises:
        `HTTP 400: "Master Admins must be assigned a part_id."`
  * Any user with the role `"Operator"` or `"Shift Incharge"` **must** have a valid `part_id` mapped.
* **Database Lookup Verification:**
  * If a `part_id` is passed, the system checks the `parts` collection. If the `part_id` does not exist:
        `HTTP 400: "Assigned Part ID not found in database"`
  * If it exists, the corresponding `part_name` is automatically populated from the part document onto the user profile.

---

## 2. Station Operations (`station_api.py`)

* **Inheritance Constraint:**
  * If `part_id` is not supplied in the creation payload, it automatically inherits the `part_id` of the creating `Master Admin` (`current_user["part_id"]`).
  * If neither the payload nor the creator profile has a `part_id`:
        `HTTP 400: "Station must be assigned a Part ID (either in payload or from Admin profile)"`
* **Station Updates:**
  * The `part_id` cannot be cleared or set to null:
        `HTTP 400: "part_id cannot be null"`
  * Any new `part_id` assigned is verified against the `parts` collection:
        `HTTP 400: "Part ID not found"`

---

## 3. Job Card Creation (`job_card_api.py`)

* **Profile Scope Constraint:**
  * When creating or generating job cards (via manual submission or bulk QR generation), the creator user profile **must** possess a valid `part_id`. If the creator has no `part_id` in their user profile:
        `HTTP 400: "User profile has no assigned Part ID"`
  * The `part_id` is validated against the `parts` collection to ensure it exists in the database.
* **Job Card Schema Binding:**
  * The created Job Cards are hard-bound with that `part_id` in the database, locking the scanned item to its production part line.
