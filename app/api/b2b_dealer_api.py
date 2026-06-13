from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from .. import schemas, auth, utils
from ..database import users_collection, b2b_coupons_collection
from .b2b_order_api import B2BOrderOperations

router = APIRouter(prefix="/api/v1/b2b-dealer", tags=["B2B Dealer"])

class B2BDealerOperations:
    @staticmethod
    def add_or_update_address(address_data: schemas.DealerCompanyAddressCreate, user_id: str) -> dict:
       
        now = utils.get_current_time()
        company_address_dict = address_data.model_dump() if hasattr(address_data, "model_dump") else address_data.dict()
        company_address_dict["updated_at"] = now

        user = users_collection.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer user with ID '{user_id}' not found"
            )

        addresses = user.get("company_addresses", [])
        
        # If the user has a legacy company_address but empty company_addresses, migrate it
        legacy_address = user.get("company_address")
        if legacy_address and not addresses:
            if "address_id" not in legacy_address or not legacy_address["address_id"]:
                legacy_address["address_id"] = f"ADDR-{now.strftime('%y%H%M%S%f')[:-3]}"
            addresses = [legacy_address]

        # Determine if we are updating an existing address
        target_id = company_address_dict.get("address_id")
        if target_id:
            # Find and update
            found = False
            for idx, addr in enumerate(addresses):
                if addr.get("address_id") == target_id:
                    # Preserve the is_business_address flag
                    company_address_dict["is_business_address"] = addr.get("is_business_address", False)
                    company_address_dict["address_id"] = target_id
                    addresses[idx] = company_address_dict
                    found = True
                    break
            if not found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Address with ID '{target_id}' not found on dealer profile"
                )
        else:
            # Generate new address ID
            new_id = f"ADDR-{now.strftime('%y%H%M%S%f')[:-3]}"
            company_address_dict["address_id"] = new_id
            addresses.append(company_address_dict)

        # Set default/primary company_address to keep backward compatibility
        primary_address = addresses[0] if addresses else None

        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "company_addresses": addresses,
                    "company_address": primary_address
                }
            }
        )

        company_address_dict["user_id"] = user_id
        return company_address_dict

    @staticmethod
    def get_address(user_id: str) -> dict:
        """
        Retrieve the primary/default company address details for a specific dealer.
        """
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer user with ID '{user_id}' not found"
            )

        company_address = user.get("company_address")
        if not company_address:
            addresses = user.get("company_addresses", [])
            if addresses:
                company_address = addresses[0]

        if not company_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company address details not found for this dealer user"
            )

        company_address["user_id"] = user_id
        return company_address

    @staticmethod
    def list_addresses(user_id: str) -> list:
        """
        Retrieve all registered company addresses for a dealer.
        """
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer user with ID '{user_id}' not found"
            )

        addresses = user.get("company_addresses", [])
        
        legacy_address = user.get("company_address")
        if legacy_address and not addresses:
            now = utils.get_current_time()
            legacy_address["address_id"] = legacy_address.get("address_id") or f"ADDR-{now.strftime('%y%H%M%S%f')[:-3]}"
            addresses = [legacy_address]
            users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"company_addresses": addresses}}
            )

        for addr in addresses:
            addr["user_id"] = user_id

        return addresses

    @staticmethod
    def delete_address(user_id: str, address_id: str) -> dict:
        """
        Delete a specific address by its address_id.
        """
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer user with ID '{user_id}' not found"
            )

        addresses = user.get("company_addresses", [])
        
        legacy_address = user.get("company_address")
        if legacy_address and not addresses:
            now = utils.get_current_time()
            legacy_address["address_id"] = legacy_address.get("address_id") or f"ADDR-{now.strftime('%y%H%M%S%f')[:-3]}"
            addresses = [legacy_address]

        target_address = next((a for a in addresses if a.get("address_id") == address_id), None)
        if not target_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Address with ID '{address_id}' not found on dealer profile"
            )

        if target_address.get("is_business_address"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business address is not deletable"
            )

        filtered_addresses = [a for a in addresses if a.get("address_id") != address_id]

        primary_address = filtered_addresses[0] if filtered_addresses else None

        users_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "company_addresses": filtered_addresses,
                    "company_address": primary_address
                }
            }
        )

        return {"detail": f"Address with ID '{address_id}' deleted successfully"}

    @staticmethod
    def get_dealer_coupons(user_id: str) -> List[dict]:
        """
        Retrieve all active coupons that are applicable to this dealer.
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Find active coupons where end_date is in the future
        query = {
            "is_active": True,
            "end_date": {"$gte": now}
        }
        coupons = list(b2b_coupons_collection.find(query))
        
        valid_coupons = []
        for c in coupons:
            # Check if dealer restriction applies
            if c.get("is_applicable_dealer"):
                dealer_ids = [str(uid).strip() for uid in c.get("applicable_dealer_ids", [])]
                if str(user_id).strip() not in dealer_ids:
                    continue # Skip if this dealer is not in the allowed list
            
            c.pop("_id", None)
            valid_coupons.append(c)
            
        return valid_coupons


# ─── API ROUTES ─────────────────────────────────────────────────

@router.post("/company/addresses", response_model=schemas.DealerCompanyAddressResponse, status_code=status.HTTP_200_OK)
def add_company_addresses_plural(
    address_data: schemas.DealerCompanyAddressCreate,
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "Super Admin", "Master Admin", "B2B Admin"]))
):
    """
    Add or update a company/business address details for the authenticated dealer (plural endpoint).
    """
    return B2BDealerOperations.add_or_update_address(address_data, current_user["user_id"])


@router.get("/company/addresses", response_model=List[schemas.DealerCompanyAddressResponse])
def get_company_addresses(
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "Super Admin", "Master Admin", "B2B Admin"]))
):
    """
    Retrieve all registered company/business addresses for the authenticated dealer.
    """
    return B2BDealerOperations.list_addresses(current_user["user_id"])


@router.delete("/company/addresses/{address_id}", status_code=status.HTTP_200_OK)
def delete_company_addresses_plural(
    address_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "Super Admin", "Master Admin", "B2B Admin"]))
):
    """
    Delete a specific company/business address for the authenticated dealer.
    """
    return B2BDealerOperations.delete_address(current_user["user_id"], address_id)


@router.get("/coupons", response_model=List[schemas.B2BCouponResponse])
def get_dealer_applicable_coupons(
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "Super Admin", "Master Admin", "B2B Admin"]))
):
    """
    Retrieve all active coupons applicable for the authenticated dealer.
    """
    return B2BDealerOperations.get_dealer_coupons(current_user["user_id"])


@router.get("/my-credit", response_model=schemas.DealerCreditStatusResponse)
def get_my_credit_status(
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "Super Admin", "Master Admin", "B2B Admin"]))
):
    """
    **Dealer** — Retrieve your own credit status, limit, outstanding, and remaining credit.
    """
    return B2BOrderOperations.get_dealer_credit_status(current_user["user_id"])
