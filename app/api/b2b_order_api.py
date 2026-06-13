from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone
from .. import schemas, auth, utils
from ..database import (
    b2b_orders_collection,
    b2b_invoices_collection,
    users_collection,
    b2b_cart_collection,
    b2b_coupons_collection,
    b2b_config_collection,
    b2b_inward_products_collection,
    b2b_gst_settings_collection
)

from .b2b_cart_api import B2BCartOperations
from ..po_generator import generate_po_pdf
from .coin_api import credit_coins, debit_coins, get_coin_config, get_wallet

router = APIRouter(prefix="/api/v1/b2b-orders", tags=["B2B Orders"])

ADMIN_ROLES = ["Super Admin", "Master Admin", "B2B Admin"]
ALL_ROLES   = ["Dealer", "Super Admin", "Master Admin", "B2B Admin"]

# ─── HELPERS ────────────────────────────────────────────────────

def get_tracking_url(courier_name: str, tracking_number: str) -> str:
    if not tracking_number:
        return ""
    c = (courier_name or "").strip().lower()
    if "delhivery" in c:
        return f"https://www.delhivery.com/track/package/{tracking_number}"
    elif "dtdc" in c:
        return f"https://www.dtdc.in/tracking/tracking_results.asp?SearchType=T&Ttype=A&ConsignmentNo={tracking_number}"
    elif "bluedart" in c or "blue dart" in c:
        return f"https://www.bluedart.com/tracking?handler=myhandler&keyname=trackdtd&keyval={tracking_number}"
    elif "fedex" in c:
        return f"https://www.fedex.com/apps/fedextrack/?tracknumbers={tracking_number}"
    elif "dhl" in c:
        return f"https://www.dhl.com/en/express/tracking.html?AWB={tracking_number}"
    elif "speed post" in c or "india post" in c:
        return f"https://www.indiapost.gov.in/_layouts/15/dop.portal.tracking/trackconsignment.aspx"
    return ""

def _enrich_order(order: dict, user_cache: dict) -> dict:
    """Strip _id, attach dealer name, po_url, tracking_url, and live coin wallet data."""
    order.pop("_id", None)
    uid = order.get("user_id")
    if uid and uid not in user_cache:
        u = users_collection.find_one(
            {"user_id": uid},
            {"first_name": 1, "last_name": 1, "mobile_number": 1}
        )
        if u:
            first = u.get("first_name", "")
            last  = u.get("last_name", "")
            user_cache[uid] = f"{first} {last}".strip() or u.get("mobile_number", uid)
        else:
            user_cache[uid] = uid
    order["ordered_by"] = user_cache.get(uid)

    # Attach PO URL and Courier Tracking URL dynamically
    order_id = order.get("order_id")
    if order_id:
        order["po_url"] = f"/api/v1/b2b-orders/{order_id}/po"

    dispatch = order.get("dispatch_details")
    if dispatch and isinstance(dispatch, dict):
        courier = dispatch.get("courier_name")
        tracking = dispatch.get("tracking_number")
        if courier and tracking:
            order["tracking_url"] = get_tracking_url(courier, tracking)
        else:
            order["tracking_url"] = None
    else:
        order["tracking_url"] = None

    # ── Coin data ─────────────────────────────────────────────────
    # Ensure per-order coin fields always have a value (0.0 for legacy orders)
    order.setdefault("coins_earned",   0.0)
    order.setdefault("coins_redeemed", 0.0)
    order.setdefault("coin_discount",  0.0)

    # Attach the dealer's CURRENT live wallet balance
    if uid:
        from .coin_api import get_wallet
        wallet = get_wallet(uid)
        order["dealer_coin_balance"] = wallet.get("coin_balance", 0.0)
    else:
        order["dealer_coin_balance"] = 0.0
    # ─────────────────────────────────────────────────────────────

    # ── Invoice & Backorder data ──────────────────────────────────
    if "invoices" not in order:
        order_id = order.get("order_id")
        if order_id:
            invoices = list(b2b_invoices_collection.find({"order_id": order_id}))
            for inv in invoices:
                inv.pop("_id", None)
                inv.pop("order_id", None)
            order["invoices"] = invoices
        else:
            order.setdefault("invoices", [])
    
    # Enrich items with backorder fields
    has_backorder = False
    for item in order.get("items", []):
        # Calculate/default quantity_invoiced
        if "quantity_invoiced" not in item:
            # Calculate from existing invoices if they exist
            total_invoiced = 0
            for inv in order.get("invoices", []):
                for inv_item in inv.get("items", []):
                    if inv_item.get("inward_id") == item.get("inward_id"):
                        total_invoiced += inv_item.get("quantity", 0)
            item["quantity_invoiced"] = total_invoiced
        
        # Calculate/default quantity_backordered based on catalog stock
        inward = b2b_inward_products_collection.find_one({"inward_id": item.get("inward_id")})
        available_stock = inward.get("quantity", 0) if (inward and inward.get("quantity") is not None) else 0
        pending_qty = max(0, item.get("quantity", 0) - item["quantity_invoiced"])
        item["quantity_backordered"] = max(0, pending_qty - available_stock)
            
        if item.get("quantity_backordered", 0) > 0:
            has_backorder = True

    order["has_backorder"] = has_backorder

    return order



def _fetch_order_or_404(order_id: str) -> dict:
    order = b2b_orders_collection.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"B2B Order '{order_id}' not found."
        )
    # Fetch invoices
    invoices = list(b2b_invoices_collection.find({"order_id": order_id}))
    for inv in invoices:
        inv.pop("_id", None)
        inv.pop("order_id", None)
    order["invoices"] = invoices
    return order


def _push_status_history(order_id: str, old_status: str, new_status: str,
                          changed_by: str, note: Optional[str] = None):
    """Append a status change record into the order's status_history array."""
    entry = {
        "from": old_status,
        "to": new_status,
        "changed_by": changed_by,
        "changed_at": utils.get_current_time(),
        "note": note,
    }
    b2b_orders_collection.update_one(
        {"order_id": order_id},
        {"$push": {"status_history": entry}}
    )

def _apply_coupon(coupon_code: str, user_id: str, subtotal: float) -> tuple[float, dict]:
    coupon = b2b_coupons_collection.find_one({"coupon_code": {"$regex": f"^{coupon_code}$", "$options": "i"}})
    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid coupon code.")
    if not coupon.get("is_active"):
        raise HTTPException(status_code=400, detail="Coupon is inactive.")
    now = datetime.now(timezone.utc)
    
    start_date = coupon.get("start_date")
    if start_date:
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if now < start_date:
            raise HTTPException(status_code=400, detail="Coupon is not yet valid.")
            
    end_date = coupon.get("end_date")
    if end_date:
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if now > end_date:
            raise HTTPException(status_code=400, detail="Coupon has expired.")
        
    if coupon.get("is_applicable_dealer"):
        allowed_ids = [str(uid).strip() for uid in coupon.get("applicable_dealer_ids", [])]
        if str(user_id).strip() not in allowed_ids:
            raise HTTPException(status_code=400, detail="Coupon is not applicable to your account.")
            
    min_order = coupon.get("minimum_order_value")
    if min_order and subtotal < min_order:
        raise HTTPException(status_code=400, detail=f"Minimum order value of {min_order} not met.")
        
    discount_val = coupon.get("discount_value", 0)
    discount_type = (coupon.get("discount_type") or "percentage").strip().lower()
    max_discount = coupon.get("max_discount_value")
    
    discount_applied = 0.0
    if discount_type == "percentage":
        discount_applied = round(subtotal * (discount_val / 100.0), 2)
        if max_discount and discount_applied > max_discount:
            discount_applied = max_discount
    elif discount_type == "flat":
        discount_applied = discount_val
        
    if discount_applied > subtotal:
        discount_applied = subtotal
        
    return round(discount_applied, 2), coupon


class B2BOrderOperations:

    @staticmethod
    def get_checkout_summary(user_id: str, address_id: Optional[str] = None,
                             shipping_address_id: Optional[str] = None,
                             billing_address_id: Optional[str] = None,
                             coupon_code: Optional[str] = None,
                             coins_to_redeem: Optional[float] = None) -> dict:
        """
        Retrieves the checkout summary without placing the order.
        """
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer user '{user_id}' not found."
            )

        # Resolve delivery address
        company_address = None
        if address_id:
            for addr in user.get("company_addresses", []):
                if addr.get("address_id") == address_id:
                    company_address = addr
                    break
            if not company_address:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Address '{address_id}' not found on dealer profile."
                )
        else:
            company_address = user.get("company_address") or \
                              (user.get("company_addresses") or [None])[0]

        # Resolve shipping address
        shipping_address = None
        if shipping_address_id:
            for addr in user.get("company_addresses", []):
                if addr.get("address_id") == shipping_address_id:
                    shipping_address = addr
                    break
            if not shipping_address:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Shipping address '{shipping_address_id}' not found on dealer profile."
                )
        else:
            # Fallback to address of type "shipping" if available
            shipping_address = next((addr for addr in user.get("company_addresses", []) if addr.get("address_type") == "shipping"), None)
            if not shipping_address:
                shipping_address = company_address

        # Resolve billing/invoice address
        billing_address = None
        if billing_address_id:
            for addr in user.get("company_addresses", []):
                if addr.get("address_id") == billing_address_id:
                    billing_address = addr
                    break
            if not billing_address:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Billing address '{billing_address_id}' not found on dealer profile."
                )
        else:
            # Fallback to address of type "billing" if available
            billing_address = next((addr for addr in user.get("company_addresses", []) if addr.get("address_type") == "billing"), None)
            if not billing_address:
                billing_address = company_address

        resolved_cart = B2BCartOperations.resolve_cart(user_id)
        
        subtotal = resolved_cart["total_price"]
        discount_applied = 0.0
        
        if coupon_code:
            discount_applied, _ = _apply_coupon(coupon_code, user_id, subtotal)
        
        # Coin redemption preview
        cfg = get_coin_config()
        coin_to_inr = cfg.get("coin_to_inr", 1.0)
        wallet = get_wallet(user_id)
        coin_balance = wallet.get("coin_balance", 0.0)

        coin_discount = 0.0
        if coins_to_redeem and coins_to_redeem > 0 and cfg.get("is_active"):
            redeemable = min(coins_to_redeem, coin_balance)
            coin_discount = round(redeemable * coin_to_inr, 2)

        total_after_coupon = round(subtotal - discount_applied, 2)
        total_price = max(0.0, round(total_after_coupon - coin_discount, 2))

        # Potential coins to earn (on the final total after all discounts)
        earn_rate = cfg.get("earn_rate_percent", 0.0) / 100.0 if cfg.get("is_active") else 0.0
        potential_coins = round(total_price * earn_rate, 4)

        return {
            "company_address": company_address,
            "shipping_address": shipping_address,
            "billing_address": billing_address,
            "items": resolved_cart["items"],
            "total_items": resolved_cart["total_items"],
            "subtotal": subtotal,
            "discount_applied": discount_applied,
            "coin_discount": coin_discount,
            "total_price": total_price,
            "coupon_code": coupon_code if discount_applied > 0 else "",
            "coin_balance": coin_balance,
            "potential_coins_earned": potential_coins,
        }

    @staticmethod
    def checkout(user_id: str, address_id: Optional[str] = None,
                 shipping_address_id: Optional[str] = None,
                 billing_address_id: Optional[str] = None,
                 payment_type: Optional[str] = None, coupon_code: Optional[str] = None,
                 coins_to_redeem: Optional[float] = None) -> dict:
        """
        Dealer checkout: captures address snapshot, resolves cart,
        applies coupon + coin redemption, creates the order, clears the active cart,
        and awards coins earned.
        """
        user = users_collection.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer user '{user_id}' not found."
            )

        # Resolve delivery address
        company_address = None
        if address_id:
            for addr in user.get("company_addresses", []):
                if addr.get("address_id") == address_id:
                    company_address = addr
                    break
            if not company_address:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Address '{address_id}' not found on dealer profile."
                )
        else:
            company_address = user.get("company_address") or \
                              (user.get("company_addresses") or [None])[0]

        if not company_address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Checkout failed: No registered company address. Please add one first."
            )

        # Resolve shipping address
        shipping_address = None
        if shipping_address_id:
            for addr in user.get("company_addresses", []):
                if addr.get("address_id") == shipping_address_id:
                    shipping_address = addr
                    break
            if not shipping_address:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Shipping address '{shipping_address_id}' not found on dealer profile."
                )
        else:
            # Fallback to address of type "shipping" if available
            shipping_address = next((addr for addr in user.get("company_addresses", []) if addr.get("address_type") == "shipping"), None)
            if not shipping_address:
                shipping_address = company_address

        # Resolve billing/invoice address
        billing_address = None
        if billing_address_id:
            for addr in user.get("company_addresses", []):
                if addr.get("address_id") == billing_address_id:
                    billing_address = addr
                    break
            if not billing_address:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Billing address '{billing_address_id}' not found on dealer profile."
                )
        else:
            # Fallback to address of type "billing" if available
            billing_address = next((addr for addr in user.get("company_addresses", []) if addr.get("address_type") == "billing"), None)
            if not billing_address:
                billing_address = company_address

        resolved_cart = B2BCartOperations.resolve_cart(user_id)
        if not resolved_cart or resolved_cart.get("total_items", 0) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Checkout failed: Cart is empty."
            )

        order_id = utils.generate_custom_id("B2B-ORD", b2b_orders_collection, "order_id", 4)
        now = utils.get_current_time()
        
        subtotal = resolved_cart["total_price"]
        discount_applied = 0.0
        
        if coupon_code:
            discount_applied, _ = _apply_coupon(coupon_code, user_id, subtotal)

        # ── Coin redemption ───────────────────────────────────────
        cfg = get_coin_config()
        coin_to_inr = cfg.get("coin_to_inr", 1.0)
        coin_discount = 0.0
        coins_redeemed = 0.0

        if coins_to_redeem and coins_to_redeem > 0 and cfg.get("is_active"):
            coin_discount = debit_coins(user_id, order_id, coins_to_redeem, coin_to_inr)
            coins_redeemed = coins_to_redeem
        # ─────────────────────────────────────────────────────────

        total_price = round(subtotal - discount_applied - coin_discount, 2)
        if total_price < 0:
            total_price = 0.0

        # Credit limit validation
        order_credit_limit = user.get("order_credit_limit")
        if order_credit_limit is None:
            cfg = b2b_config_collection.find_one({"config_id": "limits"})
            if cfg:
                order_credit_limit = cfg.get("order_credit_limit")
            if order_credit_limit is None:
                order_credit_limit = 10000.0

        if order_credit_limit is not None:
            if total_price > order_credit_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Order total ({total_price}) exceeds the single order credit limit of {order_credit_limit}."
                )
            
        overall_credit_limit = user.get("overall_credit_limit")
        if overall_credit_limit is None:
            cfg = b2b_config_collection.find_one({"config_id": "limits"})
            if cfg:
                overall_credit_limit = cfg.get("overall_credit_limit")

        if overall_credit_limit is not None:
            outstanding_orders = list(b2b_orders_collection.find({
                "user_id": user_id,
                "status": {"$ne": "Cancelled"},
                "payment_status": {"$ne": "Paid"}
            }))
            outstanding_total = sum(order.get("total_price", 0.0) for order in outstanding_orders)
            if (outstanding_total + total_price) > overall_credit_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Checkout failed: Order total and outstanding B2B orders sum ({outstanding_total + total_price}) exceeds the overall credit limit of {overall_credit_limit}."
                )
            
        order_items = []
        for item in resolved_cart["items"]:
            item_copy = dict(item)
            item_copy["quantity_invoiced"] = 0
            item_copy["quantity_backordered"] = item["quantity"]
            order_items.append(item_copy)

        order_doc = {
            "order_id":        order_id,
            "user_id":         user_id,
            "company_address": company_address,
            "shipping_address": shipping_address,
            "billing_address":  billing_address,
            "items":           order_items,
            "total_items":     resolved_cart["total_items"],
            "subtotal":        subtotal,
            "discount_applied": discount_applied,
            "coin_discount":   coin_discount,
            "coins_redeemed":  coins_redeemed,
            "total_price":     total_price,
            "coupon_code":     coupon_code if discount_applied > 0 else "",
            "status":          "Pending",
            "payment_type":    payment_type,
            "payment_status":  "Unpaid",
            "admin_note":      None,
            "cancel_reason":   None,
            "dispatch_details": None,
            "status_history":  [],
            "coins_earned":    0.0,  # will be updated after insert
            "created_at":      now,
            "updated_at":      now,
        }
        b2b_orders_collection.insert_one(order_doc)
        b2b_cart_collection.delete_many({"user_id": user_id})

        # ── Award coins earned on this order ──────────────────────
        earned = credit_coins(user_id, order_id, total_price)
        if earned > 0:
            b2b_orders_collection.update_one(
                {"order_id": order_id}, {"$set": {"coins_earned": earned}}
            )
            order_doc["coins_earned"] = earned
        # ─────────────────────────────────────────────────────────

        order_doc.pop("_id", None)
        return order_doc

    # ── LIST ORDERS ───────────────────────────────────────────────
    @staticmethod
    def list_orders(
        user_id: str,
        role: str,
        status_filter: Optional[str] = None,
        dealer_id: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> dict:
        """
        Admins see all orders with optional filters.
        Dealers see only their own orders.
        """
        query: dict = {}

        if role not in ADMIN_ROLES:
            query["user_id"] = user_id
        else:
            if dealer_id:
                query["user_id"] = dealer_id

        if status_filter:
            query["status"] = status_filter

        if search:
            # Search by order_id prefix or dealer name (via user lookup)
            user_ids_matching = [
                u["user_id"] for u in users_collection.find(
                    {"$or": [
                        {"first_name": {"$regex": search, "$options": "i"}},
                        {"last_name":  {"$regex": search, "$options": "i"}},
                        {"mobile_number": {"$regex": search, "$options": "i"}},
                    ]},
                    {"user_id": 1}
                )
            ]
            query["$or"] = [
                {"order_id": {"$regex": search, "$options": "i"}},
                {"user_id": {"$in": user_ids_matching}},
            ]

        total = b2b_orders_collection.count_documents(query)
        orders = list(
            b2b_orders_collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        user_cache: dict = {}
        enriched = [_enrich_order(o, user_cache) for o in orders]

        return {"total": total, "skip": skip, "limit": limit, "orders": enriched}

    # ── GET SINGLE ORDER ──────────────────────────────────────────
    @staticmethod
    def get_order(order_id: str, user_id: str, role: str) -> dict:
        order = _fetch_order_or_404(order_id)

        if role not in ADMIN_ROLES and order["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to view this order."
            )

        user_cache: dict = {}
        return _enrich_order(order, user_cache)

    # ── UPDATE STATUS (Admin) ─────────────────────────────────────
    @staticmethod
    def update_status(order_id: str, payload: schemas.B2BOrderStatusUpdate,
                      admin_user_id: str) -> dict:
        order = _fetch_order_or_404(order_id)
        old_status = order.get("status", "Pending")
        new_status = payload.status

        if old_status == "Cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change status of a Cancelled order."
            )
        if old_status == "Delivered" and new_status != "Cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Delivered orders can only be Cancelled."
            )

        now = utils.get_current_time()
        update_fields = {
            "status":     new_status,
            "updated_at": now,
        }
        if payload.note:
            update_fields["admin_note"] = payload.note

        b2b_orders_collection.update_one(
            {"order_id": order_id},
            {"$set": update_fields}
        )
        _push_status_history(order_id, old_status, new_status, admin_user_id, payload.note)

        updated = b2b_orders_collection.find_one({"order_id": order_id})
        user_cache: dict = {}
        return _enrich_order(updated, user_cache)

    # ── CANCEL ORDER (Admin, with reason) ────────────────────────
    @staticmethod
    def cancel_order(order_id: str, payload: schemas.B2BOrderCancelRequest,
                     admin_user_id: str) -> dict:
        order = _fetch_order_or_404(order_id)
        old_status = order.get("status", "Pending")

        if old_status == "Cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already cancelled."
            )

        now = utils.get_current_time()
        b2b_orders_collection.update_one(
            {"order_id": order_id},
            {"$set": {
                "status":        "Cancelled",
                "cancel_reason": payload.reason,
                "updated_at":    now,
            }}
        )
        _push_status_history(order_id, old_status, "Cancelled", admin_user_id, payload.reason)

        updated = b2b_orders_collection.find_one({"order_id": order_id})
        user_cache: dict = {}
        return _enrich_order(updated, user_cache)

    # ── DISPATCH ORDER (Admin) ────────────────────────────────────
    @staticmethod
    def dispatch_order(order_id: str, payload: schemas.B2BOrderDispatchUpdate,
                       admin_user_id: str) -> dict:
        order = _fetch_order_or_404(order_id)
        old_status = order.get("status", "Pending")

        if old_status in ["Delivered", "Cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot dispatch an order that is already '{old_status}'."
            )

        now = utils.get_current_time()
        dispatch_details = {
            "courier_name":       payload.courier_name,
            "tracking_number":    payload.tracking_number,
            "estimated_delivery": payload.estimated_delivery,
            "dispatched_at":      now,
            "dispatched_by":      admin_user_id,
        }

        b2b_orders_collection.update_one(
            {"order_id": order_id},
            {"$set": {
                "status":           "Dispatched",
                "dispatch_details": dispatch_details,
            "updated_at":       now,
            }}
        )
        _push_status_history(order_id, old_status, "Dispatched", admin_user_id, payload.note)

        updated = b2b_orders_collection.find_one({"order_id": order_id})
        user_cache: dict = {}
        return _enrich_order(updated, user_cache)

    # ── ADD / UPDATE ADMIN NOTE ───────────────────────────────────
    @staticmethod
    def update_note(order_id: str, payload: schemas.B2BOrderNoteUpdate) -> dict:
        order = _fetch_order_or_404(order_id)
        now = utils.get_current_time()
        b2b_orders_collection.update_one(
            {"order_id": order_id},
            {"$set": {"admin_note": payload.note, "updated_at": now}}
        )
        updated = b2b_orders_collection.find_one({"order_id": order_id})
        user_cache: dict = {}
        return _enrich_order(updated, user_cache)

    # ── UPDATE PAYMENT STATUS (Admin) ─────────────────────────────
    @staticmethod
    def update_payment_status(order_id: str, payload: schemas.B2BOrderPaymentStatusUpdate) -> dict:
        order = _fetch_order_or_404(order_id)
        now = utils.get_current_time()
        b2b_orders_collection.update_one(
            {"order_id": order_id},
            {"$set": {"payment_status": payload.payment_status, "updated_at": now}}
        )
        updated = b2b_orders_collection.find_one({"order_id": order_id})
        user_cache: dict = {}
        return _enrich_order(updated, user_cache)

    # ── GENERATE INVOICE (Admin) ──────────────────────────────────
    @staticmethod
    def generate_invoice(order_id: str, admin_user_id: str, payload: Optional[schemas.B2BInvoiceManualRequest] = None) -> dict:
        order = _fetch_order_or_404(order_id)
        if order.get("status") == "Cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot generate invoice for a cancelled order."
            )

        # 1. Resolve GST/HST settings based on shipping address state
        shipping_address = order.get("shipping_address") or order.get("company_address") or {}
        state = shipping_address.get("state")
        
        gst_setting = None
        if state:
            gst_setting = b2b_gst_settings_collection.find_one({"state": {"$regex": f"^{state}$", "$options": "i"}})
        
        if not gst_setting:
            gst_setting = b2b_gst_settings_collection.find_one({"is_default": True}) or b2b_gst_settings_collection.find_one()

        tax_type = gst_setting.get("tax_type", "GST") if gst_setting else "GST"
        tax_rate = gst_setting.get("percent", 0.0) if gst_setting else 0.0

        manual_map = {item.inward_id: item.quantity for item in payload.items} if payload else {}
        invoice_items = []
        subtotal = 0.0
        updated_items = []
        invoices_list = order.get("invoices", [])
#dfghjk
        for item in order.get("items", []):
            item_copy = dict(item)
            if "quantity_invoiced" not in item_copy:
                total_invoiced = 0
                for inv in invoices_list:
                    for inv_item in inv.get("items", []):
                        if inv_item.get("inward_id") == item_copy.get("inward_id"):
                            total_invoiced += inv_item.get("quantity", 0)
                item_copy["quantity_invoiced"] = total_invoiced

            if "quantity_backordered" not in item_copy:
                item_copy["quantity_backordered"] = max(0, item_copy.get("quantity", 0) - item_copy["quantity_invoiced"])

            pending_qty = item_copy["quantity_backordered"]
            if pending_qty <= 0:
                updated_items.append(item_copy)
                continue

            # Fetch stock in B2B catalog
            inward = b2b_inward_products_collection.find_one({"inward_id": item_copy["inward_id"]})
            available_stock = inward.get("quantity", 0) if (inward and inward.get("quantity") is not None) else 0

            # Calculate how much can be fulfilled now
            if item_copy["inward_id"] in manual_map:
                manual_qty = manual_map[item_copy["inward_id"]]
                if manual_qty > pending_qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot invoice {manual_qty} units of {item_copy['sku_no']}; only {pending_qty} are pending backorder."
                    )
                # Admin explicitly specified qty — invoice it regardless of current stock
                fulfilled_qty = manual_qty
            else:
                if payload is not None:
                    # Unspecified items in a manual request default to 0
                    fulfilled_qty = 0
                else:
                    fulfilled_qty = min(pending_qty, available_stock)

            if fulfilled_qty > 0:
                # Deduct stock from B2B inward catalog
                b2b_inward_products_collection.update_one(
                    {"inward_id": item_copy["inward_id"]},
                    {"$inc": {"quantity": -fulfilled_qty}}
                )
                item_copy["quantity_invoiced"] += fulfilled_qty
                item_copy["quantity_backordered"] -= fulfilled_qty

                item_subtotal = round(fulfilled_qty * item_copy.get("dealer_price", 0.0), 2)
                invoice_items.append({
                    "inward_id": item_copy["inward_id"],
                    "sku_no": item_copy.get("sku_no", ""),
                    "name": item_copy.get("name", ""),
                    "quantity": fulfilled_qty,
                    "dealer_price": item_copy.get("dealer_price", 0.0),
                    "subtotal": item_subtotal,
                    "currency": item_copy.get("currency", "INR")
                })
                subtotal += item_subtotal

            updated_items.append(item_copy)

        if not invoice_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No items could be invoiced. All remaining backordered items have 0 stock or were bypassed."
            )

        # 3. Calculate taxes
        tax_amount = round(subtotal * (tax_rate / 100.0), 2)
        total_with_tax = round(subtotal + tax_amount, 2)

        # 4. Save Invoice
        invoice_index = len(invoices_list) + 1
        invoice_id = f"{order_id}-INV-{invoice_index:02d}"
        invoice_doc = {
            "invoice_id": invoice_id,
            "order_id": order_id,
            "items": invoice_items,
            "subtotal": subtotal,
            "tax_type": tax_type,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total_with_tax": total_with_tax,
            "created_at": utils.get_current_time()
        }

        b2b_invoices_collection.insert_one(invoice_doc)

        old_status = order.get("status", "Pending")
        new_status = old_status
        if old_status == "Pending":
            new_status = "Confirmed"

        b2b_orders_collection.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "items": updated_items,
                    "status": new_status,
                    "updated_at": utils.get_current_time()
                }
            }
        )

        if old_status != new_status:
            _push_status_history(order_id, old_status, new_status, admin_user_id, f"Generated invoice: {invoice_id}")

        inv_to_return = dict(invoice_doc)
        inv_to_return.pop("_id", None)
        inv_to_return.pop("order_id", None)
        return inv_to_return

    # ── PREVIEW INVOICE (Admin) ───────────────────────────────────
    @staticmethod
    def preview_invoice(order_id: str, payload: Optional[schemas.B2BInvoiceManualRequest] = None) -> dict:
        order = _fetch_order_or_404(order_id)
        if order.get("status") == "Cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot preview invoice for a cancelled order."
            )

        # 1. Resolve GST/HST settings based on shipping address state (with default fallback)
        shipping_address = order.get("shipping_address") or order.get("company_address") or {}
        state = shipping_address.get("state")
        
        gst_setting = None
        if state:
            gst_setting = b2b_gst_settings_collection.find_one({"state": {"$regex": f"^{state}$", "$options": "i"}})
        
        if not gst_setting:
            gst_setting = b2b_gst_settings_collection.find_one({"is_default": True}) or b2b_gst_settings_collection.find_one()

        tax_type = gst_setting.get("tax_type", "GST") if gst_setting else "GST"
        tax_rate = gst_setting.get("percent", 0.0) if gst_setting else 0.0

        manual_map = {item.inward_id: item.quantity for item in payload.items} if payload else {}

        # 2. Simulate pending backorder items vs catalog stock
        items_to_invoice = []
        items_to_backorder = []
        subtotal = 0.0
        invoices_list = order.get("invoices", [])

        for item in order.get("items", []):
            item_copy = dict(item)
            # Default / recalculate backorder fields if missing (e.g. legacy orders)
            if "quantity_invoiced" not in item_copy:
                total_invoiced = 0
                for inv in invoices_list:
                    for inv_item in inv.get("items", []):
                        if inv_item.get("inward_id") == item_copy.get("inward_id"):
                            total_invoiced += inv_item.get("quantity", 0)
                item_copy["quantity_invoiced"] = total_invoiced

            if "quantity_backordered" not in item_copy:
                item_copy["quantity_backordered"] = max(0, item_copy.get("quantity", 0) - item_copy["quantity_invoiced"])

            pending_qty = item_copy["quantity_backordered"]
            if pending_qty <= 0:
                continue

            # Fetch stock in B2B catalog
            inward = b2b_inward_products_collection.find_one({"inward_id": item_copy["inward_id"]})
            available_stock = inward.get("quantity", 0) if (inward and inward.get("quantity") is not None) else 0

            # Calculate simulated fulfillment
            if item_copy["inward_id"] in manual_map:
                manual_qty = manual_map[item_copy["inward_id"]]
                if manual_qty > pending_qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot invoice {manual_qty} units of {item_copy['sku_no']}; only {pending_qty} are pending backorder."
                    )
                # Admin explicitly specified qty — invoice it regardless of current stock
                fulfilled_qty = manual_qty
            else:
                if payload is not None:
                    # Unspecified items in a manual request default to 0
                    fulfilled_qty = 0
                else:
                    fulfilled_qty = min(pending_qty, available_stock)

            if fulfilled_qty > 0:
                item_copy["quantity_invoiced"] += fulfilled_qty
                item_copy["quantity_backordered"] -= fulfilled_qty

                item_subtotal = round(fulfilled_qty * item_copy.get("dealer_price", 0.0), 2)
                items_to_invoice.append({
                    "inward_id": item_copy["inward_id"],
                    "sku_no": item_copy.get("sku_no", ""),
                    "name": item_copy.get("name", ""),
                    "quantity": fulfilled_qty,
                    "dealer_price": item_copy.get("dealer_price", 0.0),
                    "subtotal": item_subtotal,
                    "currency": item_copy.get("currency", "INR")
                })
                subtotal += item_subtotal

            if item_copy.get('quantity_backordered', 0) > 0:
                items_to_backorder.append(item_copy)

        # 3. Calculate taxes
        tax_amount = round(subtotal * (tax_rate / 100.0), 2)
        total_with_tax = round(subtotal + tax_amount, 2)

        return {
            "items_to_invoice": items_to_invoice,
            "items_to_backorder": items_to_backorder,
            "subtotal": subtotal,
            "tax_type": tax_type,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total_with_tax": total_with_tax
        }

    # ── BULK STATUS UPDATE (Admin) ────────────────────────────────
    @staticmethod
    def bulk_update_status(payload: schemas.B2BOrderBulkStatusUpdate,
                            admin_user_id: str) -> schemas.B2BOrderBulkResult:
        updated_ids = []
        failed_ids  = []

        for order_id in payload.order_ids:
            order = b2b_orders_collection.find_one({"order_id": order_id})
            if not order:
                failed_ids.append(order_id)
                continue

            old_status = order.get("status", "Pending")
            if old_status == "Cancelled":
                failed_ids.append(order_id)
                continue

            now = utils.get_current_time()
            b2b_orders_collection.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status":     payload.status,
                    "updated_at": now,
                    **({"admin_note": payload.note} if payload.note else {}),
                }}
            )
            _push_status_history(order_id, old_status, payload.status, admin_user_id, payload.note)
            updated_ids.append(order_id)

        return schemas.B2BOrderBulkResult(
            updated=updated_ids,
            failed=failed_ids,
            message=(
                f"{len(updated_ids)} order(s) updated to '{payload.status}'. "
                f"{len(failed_ids)} skipped."
            ),
        )

    # ── GET ORDERS BY DEALER (Admin) ──────────────────────────────
    @staticmethod
    def get_dealer_orders(dealer_id: str) -> list:
        """All orders placed by a specific dealer, newest first."""
        dealer = users_collection.find_one({"user_id": dealer_id, "role": "Dealer"})
        if not dealer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer '{dealer_id}' not found."
            )
        orders = list(b2b_orders_collection.find({"user_id": dealer_id}).sort("created_at", -1))
        user_cache: dict = {}
        return [_enrich_order(o, user_cache) for o in orders]

    @staticmethod
    def get_dealer_credit_status(dealer_id: str) -> dict:
        user = users_collection.find_one({"user_id": dealer_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dealer '{dealer_id}' not found."
            )

        order_credit_limit = user.get("order_credit_limit")
        if order_credit_limit is None:
            cfg = b2b_config_collection.find_one({"config_id": "limits"})
            if cfg:
                order_credit_limit = cfg.get("order_credit_limit")

        overall_credit_limit = user.get("overall_credit_limit")
        if overall_credit_limit is None:
            cfg = b2b_config_collection.find_one({"config_id": "limits"})
            if cfg:
                overall_credit_limit = cfg.get("overall_credit_limit")

        outstanding_orders = list(b2b_orders_collection.find({
            "user_id": dealer_id,
            "status": {"$ne": "Cancelled"},
            "payment_status": {"$ne": "Paid"}
        }))
        outstanding_total = sum(order.get("total_price", 0.0) for order in outstanding_orders)

        remaining_credit = None
        if overall_credit_limit is not None:
            remaining_credit = max(0.0, overall_credit_limit - outstanding_total)

        business_name = user.get("business_name")
        if not business_name and user.get("company_address"):
            business_name = user.get("company_address", {}).get("business_name")

        return {
            "user_id": dealer_id,
            "business_name": business_name,
            "order_credit_limit": order_credit_limit,
            "overall_credit_limit": overall_credit_limit,
            "outstanding_amount": outstanding_total,
            "remaining_credit": remaining_credit
        }


# ─── DEALER ROUTES ────────────────────────────────────────────────

@router.post("/checkout/summary", response_model=schemas.B2BCheckoutSummaryResponse)
def get_checkout_summary(
    checkout_data: Optional[schemas.B2BCheckoutRequest] = None,
    current_user: dict = Depends(auth.RoleChecker(ALL_ROLES))
):

    address_id = checkout_data.address_id if checkout_data else None
    shipping_address_id = checkout_data.shipping_address_id if checkout_data else None
    billing_address_id = checkout_data.billing_address_id if checkout_data else None
    coupon_code = checkout_data.coupon_code if checkout_data else None
    coins_to_redeem = checkout_data.coins_to_redeem if checkout_data else None
    return B2BOrderOperations.get_checkout_summary(
        current_user["user_id"], address_id, shipping_address_id, billing_address_id, coupon_code, coins_to_redeem
    )

from ..email_sender import send_po_email

def process_and_send_po(order_data: dict, dealer_user: dict):
    from ..po_generator import generate_po_pdf
    try:
        pdf_buffer = generate_po_pdf(order_data, dealer_user)
        order_id = order_data["order_id"]
        
        # Send to Dealer
        dealer_email = dealer_user.get("email")
        if dealer_email:
            send_po_email(
                to_email=dealer_email,
                subject=f"Purchase Order Confirmation - {order_id}",
                body=f"Dear {dealer_user.get('business_name', 'Dealer')},\n\nYour Purchase Order {order_id} has been generated successfully. Please find the attached PDF.\n\nThank you,\nVega Auto Accessories Ltd.",
                pdf_buffer=pdf_buffer,
                filename=f"PO_{order_id}.pdf"
            )
            
        # Send to Admin
        admin_email = "krish@motocrossindia.in"
        send_po_email(
            to_email=admin_email,
            subject=f"New Dealer Purchase Order - {order_id}",
            body=f"A new Purchase Order {order_id} has been placed by {dealer_user.get('business_name', 'Dealer')}.\n\nPlease find the attached PDF.\n\nThank you,\nVega System",
            pdf_buffer=pdf_buffer,
            filename=f"PO_{order_id}.pdf"
        )
    except Exception as e:
        print(f"Background task failed to send PO emails: {e}")

def process_and_send_invoice(order_id: str, invoice_id: str):
    from ..email_sender import send_po_email
    from ..invoice_generator import generate_invoice_pdf
    from ..database import b2b_orders_collection, b2b_invoices_collection, users_collection
    try:
        order_data = b2b_orders_collection.find_one({"order_id": order_id})
        if not order_data:
            return
            
        invoice_data = b2b_invoices_collection.find_one({"invoice_id": invoice_id})
        if not invoice_data:
            return
            
        dealer_user = users_collection.find_one({"user_id": order_data["user_id"]})
        if not dealer_user or not dealer_user.get("email"):
            return
            
        pdf_buffer = generate_invoice_pdf(order_data, invoice_data, dealer_user)
        
        is_paid = (order_data.get("payment_status") == "Paid")
        doc_type = "Invoice" if is_paid else "Proforma Invoice"
        
        send_po_email(
            to_email=dealer_user["email"],
            subject=f"{doc_type} - {invoice_id}",
            body=f"Dear {dealer_user.get('business_name', 'Dealer')},\n\nYour {doc_type} {invoice_id} has been generated successfully. Please find the attached PDF.\n\nThank you,\nVega Auto Accessories Ltd.",
            pdf_buffer=pdf_buffer,
            filename=f"{doc_type.replace(' ', '_')}_{invoice_id}.pdf"
        )
    except Exception as e:
        print(f"Background task failed to send invoice emails: {e}")

@router.post("/checkout", response_model=schemas.B2BOrderResponse, status_code=status.HTTP_201_CREATED)
def checkout_cart(
    background_tasks: BackgroundTasks,
    checkout_data: Optional[schemas.B2BCheckoutRequest] = None,
    current_user: dict = Depends(auth.RoleChecker(ALL_ROLES))
):
    address_id = checkout_data.address_id if checkout_data else None
    shipping_address_id = checkout_data.shipping_address_id if checkout_data else None
    billing_address_id = checkout_data.billing_address_id if checkout_data else None
    payment_type = checkout_data.payment_type if checkout_data else None
    coupon_code = checkout_data.coupon_code if checkout_data else None
    coins_to_redeem = checkout_data.coins_to_redeem if checkout_data else None
    
    order = B2BOrderOperations.checkout(
        current_user["user_id"], address_id, shipping_address_id, billing_address_id, payment_type, coupon_code, coins_to_redeem
    )
    
    dealer_user = users_collection.find_one({"user_id": current_user["user_id"]})
    if dealer_user:
        background_tasks.add_task(process_and_send_po, order, dealer_user)
        
    return order


@router.get("/my-orders", response_model=List[schemas.B2BOrderSummary])
def get_my_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(auth.RoleChecker(ALL_ROLES))
):

    result = B2BOrderOperations.list_orders(
        user_id=current_user["user_id"],
        role=current_user["role"],
        status_filter=status_filter,
    )
    return result["orders"]


@router.get("/", response_model=dict)
def list_all_orders(
    status_filter: Optional[str] = Query(None,  alias="status",    description="Filter by order status"),
    dealer_id:     Optional[str] = Query(None,  description="Filter by dealer user_id"),
    search:        Optional[str] = Query(None,  description="Search by order_id, dealer name or mobile"),
    skip:          int           = Query(0,     ge=0,              description="Pagination offset"),
    limit:         int           = Query(50,    ge=1, le=200,      description="Page size"),
    current_user: dict = Depends(auth.RoleChecker(ALL_ROLES))
):

    return B2BOrderOperations.list_orders(
        user_id=current_user["user_id"],
        role=current_user["role"],
        status_filter=status_filter,
        dealer_id=dealer_id,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get("/admin/dealer/{dealer_id}", response_model=List[schemas.B2BOrderSummary])
def get_orders_by_dealer(
    dealer_id: str,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):

    return B2BOrderOperations.get_dealer_orders(dealer_id)


@router.post("/admin/bulk-status", response_model=schemas.B2BOrderBulkResult)
def bulk_update_order_status(
    payload: schemas.B2BOrderBulkStatusUpdate,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):

    return B2BOrderOperations.bulk_update_status(payload, current_user["user_id"])


@router.get("/track/{order_id}", response_model=dict)
def track_order_by_id(order_id: str):
    """
    Publicly track an order's shipping/dispatch status and history by its Order ID.
    Enriches details with dynamically constructed PO PDF download URLs and courier tracking links.
    """
    order = b2b_orders_collection.find_one({"order_id": order_id})
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"B2B Order '{order_id}' not found."
        )
    
    user_cache = {}
    enriched = _enrich_order(order, user_cache)
    
    return {
        "order_id": enriched.get("order_id"),
        "status": enriched.get("status"),
        "total_items": enriched.get("total_items"),
        "total_price": enriched.get("total_price"),
        "dispatch_details": enriched.get("dispatch_details"),
        "status_history": enriched.get("status_history"),
        "created_at": enriched.get("created_at"),
        "updated_at": enriched.get("updated_at"),
        "po_url": enriched.get("po_url"),
        "tracking_url": enriched.get("tracking_url")
    }

@router.get("/{order_id}", response_model=schemas.B2BOrderResponse)
def get_order_by_id(
    order_id: str,
    current_user: dict = Depends(auth.RoleChecker(ALL_ROLES))
):
    return B2BOrderOperations.get_order(order_id, current_user["user_id"], current_user["role"])


@router.get("/{order_id}/po")
def download_purchase_order(
    order_id: str,
    current_user: dict = Depends(auth.RoleChecker(ALL_ROLES))
):
    """
    Generate and download the Purchase Order PDF for a given order.
    Accessible to both the Dealer who placed it, and any Admin.
    """
    # Verify access & get order data
    order_data = B2BOrderOperations.get_order(order_id, current_user["user_id"], current_user["role"])
    
    # Get dealer user data to populate BUYER info
    dealer_user = users_collection.find_one({"user_id": order_data["user_id"]})
    if not dealer_user:
        raise HTTPException(status_code=404, detail="Dealer details not found for this order.")
        
    pdf_buffer = generate_po_pdf(order_data, dealer_user)
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=PO_{order_id}.pdf"}
    )


@router.patch("/{order_id}/status", response_model=schemas.B2BOrderResponse)
def update_order_status(
    order_id: str,
    payload: schemas.B2BOrderStatusUpdate,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):

    return B2BOrderOperations.update_status(order_id, payload, current_user["user_id"])


@router.patch("/{order_id}/cancel", response_model=schemas.B2BOrderResponse)
def cancel_order(
    order_id: str,
    payload: schemas.B2BOrderCancelRequest,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):

    return B2BOrderOperations.cancel_order(order_id, payload, current_user["user_id"])


@router.patch("/{order_id}/dispatch", response_model=schemas.B2BOrderResponse)
def dispatch_order(
    order_id: str,
    payload: schemas.B2BOrderDispatchUpdate,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin — Dispatch Order** — mark an order as Dispatched and attach courier / tracking details.
    Stores `dispa   tch_details` with courier name, tracking number, estimated delivery, and timestamp.
    """
    return B2BOrderOperations.dispatch_order(order_id, payload, current_user["user_id"])


@router.patch("/{order_id}/note", response_model=schemas.B2BOrderResponse)
def update_order_note(
    order_id: str,
    payload: schemas.B2BOrderNoteUpdate,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    return B2BOrderOperations.update_note(order_id, payload)


@router.get("/dealer/{dealer_id}/credit", response_model=schemas.DealerCreditStatusResponse)
def get_dealer_credit_status(
    dealer_id: str,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Retrieve credit status, limit, outstanding, and remaining credit for a specific dealer.
    """
    return B2BOrderOperations.get_dealer_credit_status(dealer_id)


@router.patch("/{order_id}/payment-status", response_model=schemas.B2BOrderResponse)
def update_order_payment_status(
    order_id: str,
    payload: schemas.B2BOrderPaymentStatusUpdate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    order = B2BOrderOperations.update_payment_status(order_id, payload)
    if payload.payment_status == "Paid":
        for inv in order.get("invoices", []):
            background_tasks.add_task(process_and_send_invoice, order_id, inv.get("invoice_id"))
    return order


@router.post("/{order_id}/mark-paid", response_model=schemas.B2BOrderResponse)
def mark_order_paid(
    order_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Mark a B2B order's payment status as 'Paid'.
    """
    payload = schemas.B2BOrderPaymentStatusUpdate(payment_status="Paid")
    order = B2BOrderOperations.update_payment_status(order_id, payload)
    for inv in order.get("invoices", []):
        background_tasks.add_task(process_and_send_invoice, order_id, inv.get("invoice_id"))
    return order


from ..invoice_generator import generate_invoice_pdf

@router.post("/{order_id}/generate-invoice", response_model=schemas.B2BInvoice, status_code=status.HTTP_201_CREATED)
def generate_order_invoice(
    order_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[schemas.B2BInvoiceManualRequest] = None,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Generate an invoice for pending items. Deducts inventory based on availability.
    Items that cannot be fulfilled remain on backorder.
    """
    invoice = B2BOrderOperations.generate_invoice(order_id, current_user["user_id"], payload)
    if invoice and "invoice_id" in invoice:
        background_tasks.add_task(process_and_send_invoice, order_id, invoice["invoice_id"])
    return invoice


@router.get("/{order_id}/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    order_id: str,
    invoice_id: str,
    current_user: dict = Depends(auth.RoleChecker(ALL_ROLES))
):
    """
    **Admin / Dealer** — Generate and download the PDF for a specific B2B order invoice.
    """
    # Fetch order and verify access
    order_data = B2BOrderOperations.get_order(order_id, current_user["user_id"], current_user["role"])
    
    # Locate the invoice
    invoice_data = None
    for inv in order_data.get("invoices", []):
        if inv.get("invoice_id") == invoice_id:
            invoice_data = inv
            break
            
    if not invoice_data:
        raise HTTPException(status_code=404, detail=f"Invoice '{invoice_id}' not found on order '{order_id}'.")
        
    dealer_user = users_collection.find_one({"user_id": order_data["user_id"]})
    if not dealer_user:
        raise HTTPException(status_code=404, detail="Dealer details not found for this order.")
        
    pdf_buffer = generate_invoice_pdf(order_data, invoice_data, dealer_user)
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Invoice_{invoice_id}.pdf"}
    )


@router.post("/{order_id}/preview-invoice", response_model=schemas.B2BInvoicePreviewResponse)
def preview_order_invoice(
    order_id: str,
    payload: Optional[schemas.B2BInvoiceManualRequest] = None,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Preview order invoice details based on available stock without making any database changes.
    """
    return B2BOrderOperations.preview_invoice(order_id, payload)


@router.post("/{order_id}/preview-invoice/pdf")
def get_invoice_preview_pdf(
    order_id: str,
    payload: Optional[schemas.B2BInvoiceManualRequest] = None,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Generate and download a preview invoice PDF (watermarked with 'PREVIEW ONLY').
    """
    order_data = B2BOrderOperations.get_order(order_id, current_user["user_id"], current_user["role"])
    preview_data = B2BOrderOperations.preview_invoice(order_id, payload)
    
    # Construct a simulated invoice dictionary from the preview data
    simulated_invoice = {
        "invoice_id": f"{order_id}-PREVIEW",
        "items": preview_data["items_to_invoice"],
        "subtotal": preview_data["subtotal"],
        "tax_type": preview_data["tax_type"],
        "tax_rate": preview_data["tax_rate"],
        "tax_amount": preview_data["tax_amount"],
        "total_with_tax": preview_data["total_with_tax"],
        "created_at": utils.get_current_time()
    }
    
    dealer_user = users_collection.find_one({"user_id": order_data["user_id"]})
    if not dealer_user:
        raise HTTPException(status_code=404, detail="Dealer details not found for this order.")
        
    pdf_buffer = generate_invoice_pdf(order_data, simulated_invoice, dealer_user, is_preview=True)
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=Invoice_Preview_{order_id}.pdf"}
    )




