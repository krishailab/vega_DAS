# Super Admin API Documentation

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

## 2. Master Admin Management

### Create Master Admin
**Endpoint**: `POST /users/`
**Description**: Onboards a new organization owner.
**Payload**:
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

### Get All Users
**Endpoint**: `GET /users/`
**Description**: View all users across the entire platform.

### Update User
**Endpoint**: `PUT /users/{user_id}`
**Description**: Modify details of any user in the system.

### Delete User
**Endpoint**: `DELETE /users/{user_id}`
**Description**: Remove a user from the platform.

### View User History
**Endpoint**: `GET /scan/user-history/{user_id}`
**Description**: Monitor activities of any user in the system.

## 3. Part Catalog Management

### Create Master Part
**Endpoint**: `POST /api/create-part/`
**Description**: Defines a new part category (e.g., Helmet Shell, Visor).
**Payload**:
```json
{
  "name": "Front Bumper Assembly",
  "type": "Body Component",
  "active": true
}
```

### Get All Parts
**Endpoint**: `GET /api/create-part/`

### Update Part
**Endpoint**: `PUT /api/create-part/{part_id}`

### Delete Part
**Endpoint**: `DELETE /api/create-part/{part_id}`

## 4. Asset Management (Global Access)

Super Admins have full access to manage all assets across all Master Admins globally in the system. The following endpoints are fully authorized for the Super Admin:

* **Get Asset Dashboard**: `GET /assets/dashboard` (aggregates stats globally, or filters by a specific Master Admin if `?master_admin_id=xxx` is provided)
* **Create Category**: `POST /assets/categories`
* **Create Subcategory**: `POST /assets/subcategories`
* **Create Asset**: `POST /assets/`
* **Get All Assets**: `GET /assets/` (retrieves all assets globally, or filters by a specific Master Admin if `?master_admin_id=xxx` is provided)
* **Get Active Assigned Assets**: `GET /assets/active-assigned` (retrieves all active assignments globally, or filters by a specific Master Admin if `?master_admin_id=xxx` is provided)
* **Get Submitted Assets**: `GET /assets/submitted` (retrieves all submissions globally, or filters by a specific Master Admin if `?master_admin_id=xxx` is provided)
* **Assign Asset**: `POST /assets/{asset_id}/assign`
* **Unassign Asset**: `POST /assets/{asset_id}/unassign`
* **Get Asset Assignments**: `GET /assets/{asset_id}/assignments`
* **Submit/Return Asset**: `POST /assets/{asset_id}/submit`
* **Update Asset**: `PUT /assets/{asset_id}`
