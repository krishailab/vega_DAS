from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import Optional
from .. import schemas, auth, utils
from ..database import dealer_signup_requests_collection, users_collection
from ..email_sender import send_signup_approval_email

router = APIRouter(prefix="/dealer-signups", tags=["Dealer Signups"])

class DealerSignupOperations:
    @staticmethod
    def create_request(request: schemas.DealerSignupRequestCreate):
        # Optional validation: Check if email or mobile number already has a pending signup request
        existing_pending = dealer_signup_requests_collection.find_one({
            "$or": [
                {"email": request.email},
                {"mobile_number": request.mobile_number}
            ],
            "status": "Pending"
        })
        if existing_pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A pending signup request with this email or mobile number already exists."
            )

        request_dict = request.model_dump() if hasattr(request, "model_dump") else request.dict()
        request_dict["request_id"] = utils.generate_custom_id("DLR-REQ", dealer_signup_requests_collection, "request_id")
        request_dict["status"] = "Pending"
        now = utils.get_current_time()
        request_dict["created_at"] = now
        request_dict["updated_at"] = now
        request_dict["processed_by"] = None


        dealer_signup_requests_collection.insert_one(request_dict)
        request_dict.pop("_id", None)
        return request_dict

    @staticmethod
    def get_requests(status_filter: Optional[str] = None, page: int = 1, limit: int = 50, search: str = ""):
        query = {}
        if status_filter:
            query["status"] = status_filter
        if search:
            query["$or"] = [
                {"contact_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"mobile_number": {"$regex": search, "$options": "i"}},
                {"business_name": {"$regex": search, "$options": "i"}},
                {"request_id": {"$regex": search, "$options": "i"}}
            ]
        skip = (page - 1) * limit
        requests = list(dealer_signup_requests_collection.find(query).skip(skip).limit(limit))
        for r in requests:
            r.pop("_id", None)
        return requests

    @staticmethod
    def get_request(request_id: str):
        request = dealer_signup_requests_collection.find_one({"request_id": request_id})
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer signup request not found")
        request.pop("_id", None)
        return request

    @staticmethod
    def update_status(request_id: str, update_data: schemas.DealerSignupRequestUpdateStatus, current_user: dict, background_tasks: Optional[BackgroundTasks] = None):
        request = dealer_signup_requests_collection.find_one({"request_id": request_id})
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer signup request not found")

        target_status = "Approved" if update_data.approve else "Rejected"

        now = utils.get_current_time()

        if target_status == "Approved":
            # Block re-approval
            if request.get("status") == "Approved":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This dealer signup request has already been approved and a dealer account was created."
                )

            if not update_data.password or not update_data.password.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password is required when approving a dealer signup request."
                )

            # Check if user with same email or mobile number already exists in users_collection
            existing_user = users_collection.find_one({
                "$or": [
                    {"email": request.get("email")},
                    {"mobile_number": request.get("mobile_number")}
                ]
            })
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A dealer account with email '{request.get('email')}' or mobile '{request.get('mobile_number')}' already exists."
                )

            # Generate new custom user ID
            new_user_id = utils.generate_custom_id("DLR", users_collection, "user_id")

            # Hash the password
            hashed_password = auth.get_password_hash(update_data.password)

            # Assemble new dealer user document
            new_user = {
                "user_id": new_user_id,
                "first_name": request.get("contact_name"),
                "last_name": "Dealer",
                "age": 0,
                "gender": "N/A",
                "blood_group": "N/A",
                "employee_id": new_user_id,
                "email": request.get("email"),
                "mobile_number": request.get("mobile_number"),
                "role": "Dealer",
                "status": "Active",
                "password": hashed_password,
                "company_address": None,
                "company_addresses": [],
                "order_credit_limit": None,
                "overall_credit_limit": None
            }

            try:
                users_collection.insert_one(new_user)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create dealer account: {str(e)}"
                )

            # Send Email
            if request.get("email"):
                if background_tasks:
                    background_tasks.add_task(
                        send_signup_approval_email,
                        request.get("email"),
                        request.get("contact_name") or "Dealer",
                        update_data.password
                    )
                else:
                    try:
                        send_signup_approval_email(
                            request.get("email"),
                            request.get("contact_name") or "Dealer",
                            update_data.password
                        )
                    except Exception as email_err:
                        print(f"Failed to send email inline: {email_err}")

        update_fields = {
            "status": target_status,
            "processed_by": current_user["user_id"],
            "updated_at": now
        }

        dealer_signup_requests_collection.update_one(
            {"request_id": request_id},
            {"$set": update_fields}
        )

        updated_request = dealer_signup_requests_collection.find_one({"request_id": request_id})
        updated_request.pop("_id", None)
        return updated_request


@router.post("/", response_model=schemas.DealerSignupRequest, status_code=status.HTTP_201_CREATED)
def submit_signup_request(request: schemas.DealerSignupRequestCreate):
    return DealerSignupOperations.create_request(request)

@router.get("/", response_model=list[schemas.DealerSignupRequest])
def list_signup_requests(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    search: str = Query(""),
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return DealerSignupOperations.get_requests(status, page=page, limit=limit, search=search)

@router.get("/{request_id}", response_model=schemas.DealerSignupRequest)
def get_signup_request(
    request_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return DealerSignupOperations.get_request(request_id)

@router.put("/{request_id}/status", response_model=schemas.DealerSignupRequest)
def update_signup_request_status(
    request_id: str,
    update_data: schemas.DealerSignupRequestUpdateStatus,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(auth.RoleChecker(["Super Admin", "Master Admin", "B2B Admin"]))
):
    return DealerSignupOperations.update_status(request_id, update_data, current_user, background_tasks)
