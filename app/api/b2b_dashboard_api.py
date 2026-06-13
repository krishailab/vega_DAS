from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends
from .. import schemas, auth, utils
from ..database import (
    b2b_orders_collection,
    b2b_inward_products_collection,
    users_collection,
    product_categories_collection,
    product_subcategories_collection,
    product_brands_collection,
    product_models_collection,
    product_submodels_collection,
    product_variants_collection,
    dealer_signup_requests_collection,
)

router = APIRouter(prefix="/api/v1/b2b-admin", tags=["B2B Admin Dashboard"])

# ─── ALLOWED ROLES ───────────────────────────────────────────────
ADMIN_ROLES = ["Super Admin", "Master Admin", "B2B Admin"]


# ─── HELPER: build resolved product name ─────────────────────────
def _resolve_product_name(variant: dict, submodel: dict, model: dict, brand: dict) -> str:
    brand_name = brand.get("name", "") if brand else ""
    model_name = model.get("name", "") if model else ""
    submodel_name = submodel.get("name", "") if submodel else ""
    color = variant.get("color") or ""
    size_name = variant.get("size_name") or ""
    parts = [p for p in [brand_name, model_name, submodel_name, color, size_name] if p]
    return " ".join(parts) if parts else variant.get("sku_no", "")


# ─── HELPER: revenue time series (last N days) ───────────────────
def _build_revenue_time_series(days: int = 30) -> List[schemas.B2BRevenueTimeSeries]:
    """
    Compute day-by-day order count and revenue for the past `days` days.
    """
    tz_now = utils.get_current_time()
    cutoff = tz_now - timedelta(days=days)

    orders = list(b2b_orders_collection.find(
        {"created_at": {"$gte": cutoff}},
        {"created_at": 1, "total_price": 1, "status": 1}
    ))

    daily: dict = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
    for order in orders:
        if order.get("status", "").lower() == "cancelled":
            continue
        day_key = order["created_at"].strftime("%Y-%m-%d")
        daily[day_key]["orders"] += 1
        daily[day_key]["revenue"] += order.get("total_price", 0.0)

    # Build full date range (no gaps)
    result = []
    for i in range(days - 1, -1, -1):
        day = (tz_now - timedelta(days=i)).strftime("%Y-%m-%d")
        result.append(schemas.B2BRevenueTimeSeries(
            date=day,
            orders=daily[day]["orders"],
            revenue=round(daily[day]["revenue"], 2)
        ))
    return result


# ─── CORE DASHBOARD OPERATION ────────────────────────────────────

class B2BDashboardOperations:

    # ── SALES SUMMARY ─────────────────────────────────────────────
    @staticmethod
    def get_sales_summary() -> schemas.B2BSalesSummary:
        all_orders = list(b2b_orders_collection.find({}, {"total_price": 1, "status": 1}))

        status_counts: dict = defaultdict(int)
        total_revenue = 0.0

        for order in all_orders:
            raw_status = order.get("status", "Pending")
            status_counts[raw_status] += 1
            if raw_status.lower() != "cancelled":
                total_revenue += order.get("total_price", 0.0)

        total_orders = len(all_orders)
        avg_order_value = (total_revenue / total_orders) if total_orders else 0.0

        # Fetch current stock map for all B2B inwards
        inward_stock = {i["inward_id"]: i.get("quantity", 0) for i in b2b_inward_products_collection.find()}
        
        backorder_orders = 0
        for order in b2b_orders_collection.find({"status": {"$ne": "Cancelled"}}):
            is_backordered = False
            for item in order.get("items", []):
                inward_id = item.get("inward_id")
                available_stock = inward_stock.get(inward_id, 0)
                
                # Calculate quantity_invoiced
                total_invoiced = item.get("quantity_invoiced", 0)
                pending_qty = max(0, item.get("quantity", 0) - total_invoiced)
                
                if pending_qty > available_stock:
                    is_backordered = True
                    break
            if is_backordered:
                backorder_orders += 1

        return schemas.B2BSalesSummary(
            total_orders=total_orders,
            total_revenue=round(total_revenue, 2),
            pending_orders=status_counts.get("Pending", 0),
            confirmed_orders=status_counts.get("Confirmed", 0),
            dispatched_orders=status_counts.get("Dispatched", 0),
            delivered_orders=status_counts.get("Delivered", 0),
            cancelled_orders=status_counts.get("Cancelled", 0),
            avg_order_value=round(avg_order_value, 2),
            backorder_orders=backorder_orders
        )

    # ── DEALER SUMMARY ────────────────────────────────────────────
    @staticmethod
    def get_dealer_summary() -> schemas.B2BDealerSummary:
        tz_now = utils.get_current_time()
        month_start = tz_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        dealers = list(users_collection.find({"role": "Dealer"}, {
            "user_id": 1, "status": 1, "created_at": 1
        }))

        total_dealers = len(dealers)
        active_dealers = sum(1 for d in dealers if d.get("status", "Active") == "Active")
        inactive_dealers = total_dealers - active_dealers
        new_this_month = sum(1 for d in dealers if d.get("created_at") and d["created_at"] >= month_start)

        # dealers who placed at least one order
        dealers_with_orders = len(b2b_orders_collection.distinct("user_id"))

        return schemas.B2BDealerSummary(
            total_dealers=total_dealers,
            active_dealers=active_dealers,
            inactive_dealers=inactive_dealers,
            new_dealers_this_month=new_this_month,
            dealers_with_orders=dealers_with_orders,
        )

    # ── PRODUCT SUMMARY ───────────────────────────────────────────
    @staticmethod
    def get_product_summary() -> schemas.B2BProductSummary:
        inward_docs = list(b2b_inward_products_collection.find({}, {
            "is_active": 1, "is_featured": 1, "is_new_arrival": 1, "is_best_seller": 1
        }))

        total_inwarded = len(inward_docs)
        active_products = sum(1 for i in inward_docs if i.get("is_active"))
        inactive_products = total_inwarded - active_products
        featured = sum(1 for i in inward_docs if i.get("is_featured"))
        new_arrivals = sum(1 for i in inward_docs if i.get("is_new_arrival"))
        best_sellers = sum(1 for i in inward_docs if i.get("is_best_seller"))

        total_categories = product_categories_collection.count_documents({"is_active": True})
        total_brands = product_brands_collection.count_documents({"is_active": True})

        return schemas.B2BProductSummary(
            total_inwarded=total_inwarded,
            active_products=active_products,
            inactive_products=inactive_products,
            featured_products=featured,
            new_arrivals=new_arrivals,
            best_sellers=best_sellers,
            total_categories=total_categories,
            total_brands=total_brands,
        )

    # ── TOP PRODUCTS ──────────────────────────────────────────────
    @staticmethod
    def get_top_products(limit: int = 10) -> List[schemas.B2BTopProduct]:
        """
        Aggregate sold quantities per inward_id from completed (non-cancelled) orders.
        """
        all_orders = list(b2b_orders_collection.find(
            {"status": {"$ne": "Cancelled"}},
            {"items": 1}
        ))

        product_stats: dict = defaultdict(lambda: {"quantity": 0, "revenue": 0.0})
        for order in all_orders:
            for item in order.get("items", []):
                inward_id = item.get("inward_id")
                if inward_id:
                    product_stats[inward_id]["quantity"] += item.get("quantity", 0)
                    product_stats[inward_id]["revenue"] += item.get("subtotal", 0.0)

        # Sort by quantity descending
        sorted_products = sorted(
            product_stats.items(),
            key=lambda x: x[1]["quantity"],
            reverse=True
        )[:limit]

        # Prefetch lookup tables
        inwards_by_id = {i["inward_id"]: i for i in b2b_inward_products_collection.find()}
        variants_by_id = {v["variant_id"]: v for v in product_variants_collection.find()}
        submodels_by_id = {sm["submodel_id"]: sm for sm in product_submodels_collection.find()}
        models_by_id = {m["model_id"]: m for m in product_models_collection.find()}
        brands_by_id = {b["brand_id"]: b for b in product_brands_collection.find()}

        top_products = []
        for inward_id, stats in sorted_products:
            inward = inwards_by_id.get(inward_id)
            if not inward:
                continue
            variant = variants_by_id.get(inward.get("variant_id", ""))
            submodel = submodels_by_id.get(variant.get("submodel_id", "")) if variant else None
            model = models_by_id.get(submodel.get("model_id", "")) if submodel else None
            brand = brands_by_id.get(model.get("brand_id", "")) if model else None

            name = _resolve_product_name(variant or {}, submodel or {}, model or {}, brand or {})
            images = (variant or {}).get("product_images", [])
            image = images[0] if images else ((submodel or {}).get("image"))

            top_products.append(schemas.B2BTopProduct(
                inward_id=inward_id,
                variant_id=inward.get("variant_id", ""),
                sku_no=inward.get("sku_no", ""),
                name=name,
                image=image,
                total_quantity_sold=stats["quantity"],
                total_revenue=round(stats["revenue"], 2),
            ))

        return top_products

    # ── TOP DEALERS ───────────────────────────────────────────────
    @staticmethod
    def get_top_dealers(limit: int = 10) -> List[schemas.B2BTopDealer]:
        """
        Rank dealers by total spend across all non-cancelled orders.
        """
        all_orders = list(b2b_orders_collection.find(
            {"status": {"$ne": "Cancelled"}},
            {"user_id": 1, "total_price": 1, "created_at": 1}
        ))

        dealer_stats: dict = defaultdict(lambda: {
            "total_orders": 0, "total_spent": 0.0, "last_order_at": None
        })

        for order in all_orders:
            uid = order.get("user_id")
            if not uid:
                continue
            dealer_stats[uid]["total_orders"] += 1
            dealer_stats[uid]["total_spent"] += order.get("total_price", 0.0)
            ts = order.get("created_at")
            if ts and (dealer_stats[uid]["last_order_at"] is None or ts > dealer_stats[uid]["last_order_at"]):
                dealer_stats[uid]["last_order_at"] = ts

        sorted_dealers = sorted(
            dealer_stats.items(),
            key=lambda x: x[1]["total_spent"],
            reverse=True
        )[:limit]

        top_dealers = []
        for uid, stats in sorted_dealers:
            user = users_collection.find_one({"user_id": uid}, {
                "first_name": 1, "last_name": 1, "mobile_number": 1
            })
            if not user:
                dealer_name = uid
                mobile = None
            else:
                first = user.get("first_name", "")
                last = user.get("last_name", "")
                dealer_name = f"{first} {last}".strip() or uid
                mobile = user.get("mobile_number")

            top_dealers.append(schemas.B2BTopDealer(
                user_id=uid,
                dealer_name=dealer_name,
                mobile_number=mobile,
                total_orders=stats["total_orders"],
                total_spent=round(stats["total_spent"], 2),
                last_order_at=stats["last_order_at"],
            ))

        return top_dealers

    # ── RECENT ORDERS ─────────────────────────────────────────────
    @staticmethod
    def get_recent_orders(limit: int = 10) -> List[schemas.B2BOrderSummary]:
        orders = list(b2b_orders_collection.find().sort("created_at", -1).limit(limit))

        user_cache: dict = {}
        result = []
        for order in orders:
            order.pop("_id", None)
            uid = order.get("user_id")
            if uid and uid not in user_cache:
                u = users_collection.find_one({"user_id": uid}, {
                    "first_name": 1, "last_name": 1, "mobile_number": 1
                })
                if u:
                    first = u.get("first_name", "")
                    last = u.get("last_name", "")
                    user_cache[uid] = f"{first} {last}".strip() or u.get("mobile_number", uid)
                else:
                    user_cache[uid] = uid

            order["ordered_by"] = user_cache.get(uid)
            result.append(order)

        return result

    # ── BACKORDERED VARIANTS ──────────────────────────────────────
    @staticmethod
    def get_backordered_variants() -> List[schemas.B2BBackorderedVariant]:
        from ..database import b2b_invoices_collection
        orders = list(b2b_orders_collection.find({"status": {"$ne": "Cancelled"}}))
        inwards_by_id = {i["inward_id"]: i for i in b2b_inward_products_collection.find()}
        
        backorders_by_inward = defaultdict(int)
        backorder_orders_by_inward = defaultdict(set)
        
        for order in orders:
            invoices = list(b2b_invoices_collection.find({"order_id": order["order_id"]}))
            for item in order.get("items", []):
                inward_id = item.get("inward_id")
                if not inward_id:
                    continue
                    
                total_invoiced = item.get("quantity_invoiced")
                if total_invoiced is None:
                    total_invoiced = 0
                    for inv in invoices:
                        for inv_item in inv.get("items", []):
                            if inv_item.get("inward_id") == inward_id:
                                total_invoiced += inv_item.get("quantity", 0)
                                
                available_stock = inwards_by_id.get(inward_id, {}).get("quantity", 0)
                pending_qty = max(0, item.get("quantity", 0) - total_invoiced)
                backordered_qty = max(0, pending_qty - available_stock)
                if backordered_qty > 0:
                    backorders_by_inward[inward_id] += backordered_qty
                    backorder_orders_by_inward[inward_id].add(order["order_id"])
                    
        variants_by_id = {v["variant_id"]: v for v in product_variants_collection.find()}
        submodels_by_id = {sm["submodel_id"]: sm for sm in product_submodels_collection.find()}
        models_by_id = {m["model_id"]: m for m in product_models_collection.find()}
        brands_by_id = {b["brand_id"]: b for b in product_brands_collection.find()}

        backordered_variants = []
        for inward_id, bo_qty in backorders_by_inward.items():
            inward = inwards_by_id.get(inward_id)
            if not inward:
                continue
            variant = variants_by_id.get(inward.get("variant_id", ""))
            submodel = submodels_by_id.get(variant.get("submodel_id", "")) if variant else None
            model = models_by_id.get(submodel.get("model_id", "")) if submodel else None
            brand = brands_by_id.get(model.get("brand_id", "")) if model else None

            name = _resolve_product_name(variant or {}, submodel or {}, model or {}, brand or {})
            available_stock = inward.get("quantity") if (inward and inward.get("quantity") is not None) else 0
            order_ids_list = sorted(list(backorder_orders_by_inward[inward_id]))

            backordered_variants.append(schemas.B2BBackorderedVariant(
                variant_id=inward.get("variant_id", ""),
                sku_no=inward.get("sku_no", ""),
                name=name,
                backorder_quantity=bo_qty,
                available_stock=available_stock,
                order_ids=order_ids_list
            ))
            
        return backordered_variants

    # ── UNIFIED DASHBOARD ─────────────────────────────────────────
    @staticmethod
    def get_full_dashboard(top_n: int = 10, series_days: int = 30) -> schemas.B2BAdminDashboard:
        return schemas.B2BAdminDashboard(
            sales_summary=B2BDashboardOperations.get_sales_summary(),
            dealer_summary=B2BDashboardOperations.get_dealer_summary(),
            product_summary=B2BDashboardOperations.get_product_summary(),
            revenue_time_series=_build_revenue_time_series(series_days),
            top_products=B2BDashboardOperations.get_top_products(top_n),
            top_dealers=B2BDashboardOperations.get_top_dealers(top_n),
            recent_orders=B2BDashboardOperations.get_recent_orders(top_n),
            backordered_variants=B2BDashboardOperations.get_backordered_variants()
        )


# ─── API ROUTES ─────────────────────────────────────────────────

@router.get("/dashboard", response_model=schemas.B2BAdminDashboard)
def get_b2b_admin_dashboard(
    top_n: int = 10,
    series_days: int = 30,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **B2B Admin Dashboard** — unified overview.

    Returns a single JSON object containing:
    - **sales_summary**: order counts by status, total revenue, average order value
    - **dealer_summary**: total / active / new dealers, dealers who have ordered
    - **product_summary**: inwarded product stats, category & brand counts
    - **revenue_time_series**: day-by-day revenue & order counts (default last 30 days)
    - **top_products**: top-N products ranked by units sold (excludes cancelled orders)
    - **top_dealers**: top-N dealers ranked by total spend (excludes cancelled orders)
    - **recent_orders**: latest N orders across all dealers

    Query params:
    - `top_n` (default 10) — how many top products / top dealers / recent orders to return
    - `series_days` (default 30) — how many past days to cover in revenue_time_series
    """
    return B2BDashboardOperations.get_full_dashboard(top_n=top_n, series_days=series_days)


@router.get("/dashboard/sales", response_model=schemas.B2BSalesSummary)
def get_b2b_sales_summary(
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **B2B Sales Summary** — order counts by status, total revenue, and average order value.
    """
    return B2BDashboardOperations.get_sales_summary()


@router.get("/dashboard/products", response_model=schemas.B2BProductSummary)
def get_b2b_product_summary(
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **B2B Product Summary** — breakdown of inwarded products by active/inactive status,
    feature flags (featured, new arrival, best seller), and master catalogue size.
    """
    return B2BDashboardOperations.get_product_summary()


@router.get("/dashboard/dealers", response_model=schemas.B2BDealerSummary)
def get_b2b_dealer_summary(
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **B2B Dealer Summary** — total, active, inactive dealers, new registrations this month,
    and how many dealers have placed at least one order.
    """
    return B2BDashboardOperations.get_dealer_summary()


@router.get("/dashboard/revenue-series", response_model=List[schemas.B2BRevenueTimeSeries])
def get_b2b_revenue_time_series(
    days: int = 30,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Revenue Time Series** — daily order count and revenue for the past `days` days.
    Cancelled orders are excluded from revenue calculations.
    """
    return _build_revenue_time_series(days)


@router.get("/dashboard/top-products", response_model=List[schemas.B2BTopProduct])
def get_b2b_top_products(
    limit: int = 10,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Top Products** — products ranked by total units sold across non-cancelled orders,
    enriched with resolved product names and images.
    """
    return B2BDashboardOperations.get_top_products(limit)


@router.get("/dashboard/top-dealers", response_model=List[schemas.B2BTopDealer])
def get_b2b_top_dealers(
    limit: int = 10,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Top Dealers** — dealers ranked by total spend across non-cancelled orders,
    enriched with dealer name and contact details.
    """
    return B2BDashboardOperations.get_top_dealers(limit)


@router.get("/dashboard/recent-orders", response_model=List[schemas.B2BOrderSummary])
def get_b2b_recent_orders(
    limit: int = 10,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Recent Orders** — latest `limit` B2B orders across all dealers, sorted newest-first.
    """
    return B2BDashboardOperations.get_recent_orders(limit)


@router.get("/dashboard/backorders", response_model=List[schemas.B2BBackorderedVariant])
def get_b2b_backorders(
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    return B2BDashboardOperations.get_backordered_variants()
