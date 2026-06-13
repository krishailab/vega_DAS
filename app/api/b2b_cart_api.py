from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from .. import schemas, auth, utils
from ..database import (
    b2b_cart_collection,
    b2b_inward_products_collection,
    product_variants_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection
)

router = APIRouter(prefix="/api/v1/b2b-cart", tags=["B2B Cart"])

class B2BCartOperations:
    @staticmethod
    def resolve_cart(user_id: str) -> dict:
        """
        Helper method to retrieve and fully resolve the dealer's cart items.
        """
        cart_items = list(b2b_cart_collection.find({"user_id": user_id}))
        inward_ids = list(set(item["inward_id"] for item in cart_items if item.get("inward_id")))
        inwards_by_id = {i["inward_id"]: i for i in b2b_inward_products_collection.find({"inward_id": {"$in": inward_ids}})}

        variant_ids = list(set(inw["variant_id"] for inw in inwards_by_id.values() if inw.get("variant_id")))
        variants_by_id = {v["variant_id"]: v for v in product_variants_collection.find({"variant_id": {"$in": variant_ids}})}

        submodel_ids = list(set(v["submodel_id"] for v in variants_by_id.values() if v.get("submodel_id")))
        submodels_by_id = {sm["submodel_id"]: sm for sm in product_submodels_collection.find({"submodel_id": {"$in": submodel_ids}})}

        model_ids = list(set(sm["model_id"] for sm in submodels_by_id.values() if sm.get("model_id")))
        models_by_id = {m["model_id"]: m for m in product_models_collection.find({"model_id": {"$in": model_ids}})}

        brand_ids = list(set(m["brand_id"] for m in models_by_id.values() if m.get("brand_id")))
        brands_by_id = {b["brand_id"]: b for b in product_brands_collection.find({"brand_id": {"$in": brand_ids}})}

        resolved_items = []
        total_items = 0
        total_price = 0.0

        for item in cart_items:
            inward_id = item["inward_id"]
            quantity = item["quantity"]

            inward = inwards_by_id.get(inward_id)
            if not inward:
                # If the product was deleted from B2B catalog, we skip it
                continue

            variant_id = inward["variant_id"]
            variant = variants_by_id.get(variant_id)
            if not variant:
                continue

            submodel = submodels_by_id.get(variant["submodel_id"])
            model = models_by_id.get(submodel["model_id"]) if submodel else None
            brand = brands_by_id.get(model["brand_id"]) if model else None

            brand_name = brand.get("name") if brand else ""
            model_name = model.get("name") if model else ""
            submodel_name = submodel.get("name") if submodel else ""
            color = variant.get("color") or ""
            size_name = variant.get("size_name") or ""

            # Construct beautifully resolved name
            name_parts = [part for part in [brand_name, model_name, submodel_name, color, size_name] if part]
            resolved_name = " ".join(name_parts) if name_parts else variant.get("sku_no")

            # First product image or submodel graphic
            images_list = variant.get("product_images", [])
            image_url = images_list[0] if images_list else (submodel.get("image") if submodel else None)

            dealer_price = inward["dealer_price"]
            subtotal = round(dealer_price * quantity, 2)

            inward_currency = inward.get("currency", "INR")
            mrp_raw = variant.get("mrp")
            mrp_resolved = None
            if isinstance(mrp_raw, dict):
                mrp_resolved = mrp_raw.get(inward_currency)
                if mrp_resolved is None:
                    mrp_resolved = mrp_raw.get("INR")
                if mrp_resolved is None and mrp_raw:
                    mrp_resolved = next(iter(mrp_raw.values()), None)
            elif isinstance(mrp_raw, (int, float)):
                mrp_resolved = float(mrp_raw)

            resolved_items.append({
                "inward_id": inward_id,
                "variant_id": variant_id,
                "sku_no": inward["sku_no"],
                "name": resolved_name,
                "image": image_url,
                "dealer_price": dealer_price,
                "currency": inward_currency,
                "mrp": mrp_resolved,
                "quantity": quantity,
                "subtotal": subtotal,
                "is_individual": inward["is_individual"],
                "is_carton": inward["is_carton"],
                "carton_box_size": variant.get("carton_box_size")
            })

            total_items += quantity
            total_price = round(total_price + subtotal, 2)

        return {
            "items": resolved_items,
            "total_items": total_items,
            "total_price": total_price
        }

    @staticmethod
    def add_to_cart(cart_add: schemas.B2BCartItemAdd, user_id: str) -> dict:
        # 1. Verify B2B inwarded product exists and is active
        inward = b2b_inward_products_collection.find_one({"inward_id": cart_add.inward_id})
        if not inward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"B2B inwarded product with ID '{cart_add.inward_id}' does not exist"
            )

        if not inward.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"B2B inwarded product with ID '{cart_add.inward_id}' is currently inactive"
            )

        if cart_add.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity to add must be greater than zero"
            )

        # 2. Check if product already exists in the dealer's cart
        existing = b2b_cart_collection.find_one({"user_id": user_id, "inward_id": cart_add.inward_id})
        now = utils.get_current_time()

        if existing:
            new_quantity = existing["quantity"] + cart_add.quantity
            b2b_cart_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"quantity": new_quantity, "updated_at": now}}
            )
        else:
            cart_doc = {
                "user_id": user_id,
                "inward_id": cart_add.inward_id,
                "quantity": cart_add.quantity,
                "created_at": now,
                "updated_at": now
            }
            b2b_cart_collection.insert_one(cart_doc)

        return B2BCartOperations.resolve_cart(user_id)

    @staticmethod
    def update_quantity(inward_id: str, cart_update: schemas.B2BCartItemUpdate, user_id: str) -> dict:
        existing = b2b_cart_collection.find_one({"user_id": user_id, "inward_id": inward_id})
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID '{inward_id}' is not in your cart"
            )

        new_quantity = cart_update.quantity
        if new_quantity <= 0:
            # Delete from cart if quantity is 0 or less
            b2b_cart_collection.delete_one({"_id": existing["_id"]})
        else:
            b2b_cart_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"quantity": new_quantity, "updated_at": utils.get_current_time()}}
            )

        return B2BCartOperations.resolve_cart(user_id)

    @staticmethod
    def remove_item(inward_id: str, user_id: str) -> dict:
        existing = b2b_cart_collection.find_one({"user_id": user_id, "inward_id": inward_id})
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID '{inward_id}' is not in your cart"
            )

        b2b_cart_collection.delete_one({"_id": existing["_id"]})
        return B2BCartOperations.resolve_cart(user_id)

    @staticmethod
    def clear_cart(user_id: str) -> dict:
        b2b_cart_collection.delete_many({"user_id": user_id})
        return {
            "items": [],
            "total_items": 0,
            "total_price": 0.0
        }


# ─── API ROUTES ─────────────────────────────────────────────────

@router.get("/", response_model=schemas.B2BCartResponse)
def get_cart(
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "B2B Admin", "Super Admin", "Master Admin"]))
):
    """
    Retrieve all resolved cart items and total calculations for the authenticated dealer.
    """
    return B2BCartOperations.resolve_cart(current_user["user_id"])


@router.post("/items", response_model=schemas.B2BCartResponse, status_code=status.HTTP_201_CREATED)
def add_item_to_cart(
    cart_add: schemas.B2BCartItemAdd,
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "B2B Admin", "Super Admin", "Master Admin"]))
):
    """
    Add a B2B active inwarded product to the cart. If already present, increments quantity.
    """
    return B2BCartOperations.add_to_cart(cart_add, current_user["user_id"])


@router.put("/items/{inward_id}", response_model=schemas.B2BCartResponse)
def update_cart_item_quantity(
    inward_id: str,
    cart_update: schemas.B2BCartItemUpdate,
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "B2B Admin", "Super Admin", "Master Admin"]))
):
    """
    Update the quantity of an item in the cart. If quantity is 0 or less, removes item.
    """
    return B2BCartOperations.update_quantity(inward_id, cart_update, current_user["user_id"])


@router.delete("/items/{inward_id}", response_model=schemas.B2BCartResponse)
def remove_cart_item(
    inward_id: str,
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "B2B Admin", "Super Admin", "Master Admin"]))
):
    """
    Remove a specific item from the dealer's cart.
    """
    return B2BCartOperations.remove_item(inward_id, current_user["user_id"])


@router.delete("/", response_model=schemas.B2BCartResponse)
def clear_dealer_cart(
    current_user: dict = Depends(auth.RoleChecker(["Dealer", "B2B Admin", "Super Admin", "Master Admin"]))
):
    """
    Clear all items in the dealer's cart.
    """
    return B2BCartOperations.clear_cart(current_user["user_id"])
