# Kiosk Management API Documentation

This document explains the APIs required for the Kiosk Mobile Application to communicate with the Admin Backend. It covers branding, configuration, secure exit pin verification, and administrative CRUD endpoints.

## Base URL
`https://your-domain.com/api/v1/kiosk`

---

## 1. Kiosk Device APIs

These endpoints are accessed directly by the Kiosk Mobile Applications. They are completely public and do not require device IDs or tokens in the headers.

### A. Get Kiosk Configuration
Retrieves custom branding, themes, and Google Drive APK update download link globally. Highly recommended on app startup and every hour.

* **Endpoint**: `GET /config`
* **Query Parameters**:
  - `master_admin_id`: `string` (Optional. If provided, resolves the custom Kiosk configuration for that Master Admin's branch/store. Otherwise, falls back to the first configuration).
* **Success Response (`200 OK`)**:
  ```json
  {
    "status": "success",
    "data": {
      "device_id": "KSK0001",
      "theme": {
        "primary_color": "#0047AB",
        "secondary_color": "#FFC107",
        "background_color": "#FFFFFF",
        "logo_url": "https://your-domain.com/assets/images/kiosk_logo.png",
        "splash_image_url": "https://your-domain.com/assets/images/splash_bg.png"
      },
      "is_update_mandatory": true,
      "apk_download_url": "https://drive.google.com/uc?export=download&id=FILE_ID"
    }
  }
  ```

* **Backend Behavior Notes**:
  - **Auto-Onboarding**: If no configuration exists, the system automatically registers a default configuration generating a sequential device ID (e.g. `KSK0001`) and kiosk token (e.g. `KTK0001`) dynamically via our custom primary key generator.
  - **Caching**: The backend caches the config response globally per `master_admin_id` in-memory to minimize MongoDB read overhead. The cache is automatically cleared when an admin updates settings.

---

### B. Verify Admin PIN / Deactivate Kiosk
Used when admins want to exit kiosk mode or access maintenance settings.

* **Endpoint**: `POST /verify-pin`
* **Query Parameters**:
  - `master_admin_id`: `string` (Optional. Verifies exit PIN against that specific Master Admin's Kiosk configuration).
* **Request Payload**:
  ```json
  {
    "pin": "847592",
    "action": "deactivate_kiosk"
  }
  ```
* **Success Response (`200 OK`)**:
  ```json
  {
    "status": "success",
    "message": "PIN verified successfully",
    "data": {
      "is_valid": true,
      "access_granted_until": "2026-05-18T19:00:00Z"
    }
  }
  ```
* **Error Response (`400 Bad Request` / `404 Not Found`)**:
  ```json
  {
    "status": "error",
    "message": "Invalid PIN provided",
    "data": {
      "is_valid": false
    }
  }
  ```

---

## 2. Kiosk Administration CRUD APIs

These endpoints are used by **Super Admins** or **Master Admins** in the management dashboard to coordinate themes, settings, and versions across various physical stores or branches.

* **Authorization**: Bearer JWT token of an Admin (enforced by `Depends(auth.RoleChecker(["Super Admin", "Master Admin"]))`)

### Multi-Tenant Access Controls:
1. **Master Admin**:
   - Each Master Admin is allowed **exactly one** kiosk configuration in the system.
   - Master Admins can only view, update, or delete their own configuration (`master_admin_id` matching their own `user_id`). Trying to update or delete configurations owned by other Master Admins results in a `403 Forbidden` response.
2. **Super Admin**:
   - Super Admins can manage all kiosks globally in the system.
   - They can register Kiosks for any specific Master Admin by supplying the `master_admin_id` parameter.
   - They can view, update, or delete any kiosk configuration.

---

### A. Register Kiosk Config
Registers a kiosk configuration with branding assets.
* **Endpoint**: `POST /`
* **Content-Type**: `multipart/form-data`
* **Form Parameters**:
  - `admin_pin`: `998877` (Required)
  - `primary_color`: `#FF5733` (Required)
  - `secondary_color`: `#33FF57` (Required)
  - `background_color`: `#000000` (Required)
  - `logo`: [Upload Logo File] (Optional)
  - `splash_image`: [Upload Splash Screen Image File] (Optional)
  - `is_update_mandatory`: `true` (Required)
  - `apk_download_url`: `https://drive.google.com/uc?export=download&id=FILE_ID_B` (Required)
  - `master_admin_id`: `string` (Optional. Only usable by Super Admins to assign a kiosk to a specific Master Admin. For Master Admins, this parameter is ignored and automatically resolved to their own `user_id`).

### B. List Kiosk Configs
* **Endpoint**: `GET /`
* **Response**: Returns a list containing only the Master Admin's own kiosk configuration, or all configurations if called by a Super Admin.

### C. Update Kiosk Config
* **Endpoint**: `PUT /{device_id}`
* **Content-Type**: `multipart/form-data`
* **Form Parameters**: (Supports partial/optional updates of any parameters)
  - `admin_pin` (Optional)
  - `primary_color` (Optional)
  - `secondary_color` (Optional)
  - `background_color` (Optional)
  - `logo` [Upload New Logo File] (Optional)
  - `splash_image` [Upload New Splash Screen File] (Optional)
  - `is_update_mandatory` (Optional)
  - `apk_download_url` (Optional)

### D. Delete Kiosk Config
Removes a kiosk configuration from the database and invalidates the cache.
* **Endpoint**: `DELETE /{device_id}`
