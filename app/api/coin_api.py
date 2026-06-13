"""
Coin / Rewards System API
=========================
• Admin can configure the earn-rate (% of order total that becomes coins) and
  how many INR each coin is worth.
• Coins are credited automatically after an order is placed.
• Dealers can redeem coins at checkout to get a discount on their order.
• Full transaction ledger is maintained per dealer.

Collections used (defined in database.py):
  coin_config_collection       — single document holding global settings
  coin_wallets_collection      — one doc per dealer  { user_id, coin_balance, ... }
  coin_transactions_collection — append-only ledger of every credit / debit
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from typing import List, Optional
from .. import schemas, auth, utils
from ..database import (
    coin_config_collection,
    coin_wallets_collection,
    coin_transactions_collection,
    users_collection,
)

router = APIRouter(prefix="/api/v1/coins", tags=["Coin Rewards"])

ADMIN_ROLES  = ["Super Admin", "Master Admin", "B2B Admin"]
DEALER_ROLES = ["Dealer", "Super Admin", "Master Admin", "B2B Admin"]

# ── Singleton config key ──────────────────────────────────────────
_CONFIG_KEY = "global"


# ─────────────────────────────────────────────────────────────────
# INTERNAL HELPERS  (used by b2b_order_api too)
# ─────────────────────────────────────────────────────────────────

def get_coin_config() -> dict:
    """Return the single global config doc, creating default if absent."""
    cfg = coin_config_collection.find_one({"key": _CONFIG_KEY})
    if not cfg:
        cfg = {
            "key": _CONFIG_KEY,
            "earn_rate_percent": 2.0,
            "coin_to_inr": 1.0,
            "is_active": True,
            "updated_at": utils.get_current_time(),
            "updated_by": "system",
        }
        coin_config_collection.insert_one(cfg)
    cfg.pop("_id", None)
    return cfg


def get_wallet(user_id: str) -> dict:
    """Return or lazily create a dealer's coin wallet."""
    wallet = coin_wallets_collection.find_one({"user_id": user_id})
    if not wallet:
        wallet = {
            "user_id": user_id,
            "coin_balance": 0.0,
            "total_earned": 0.0,
            "total_redeemed": 0.0,
            "last_updated": utils.get_current_time(),
        }
        coin_wallets_collection.insert_one(wallet)
    wallet.pop("_id", None)
    return wallet


def credit_coins(user_id: str, order_id: str, order_total: float) -> float:
    """
    Calculate coins to award based on the global config, credit them to the
    dealer's wallet, and write a CREDIT transaction.
    Returns the number of coins credited (0 if rewards disabled or rate is 0).
    """
    cfg = get_coin_config()
    if not cfg.get("is_active") or cfg.get("earn_rate_percent", 0) <= 0:
        return 0.0

    earn_rate = cfg["earn_rate_percent"] / 100.0
    coins = round(order_total * earn_rate, 4)
    if coins <= 0:
        return 0.0

    now = utils.get_current_time()
    txn_id = utils.generate_custom_id("CTXN", coin_transactions_collection, "txn_id")

    coin_transactions_collection.insert_one({
        "txn_id":       txn_id,
        "user_id":      user_id,
        "txn_type":     "CREDIT",
        "coins":        coins,
        "reference_id": order_id,
        "note":         f"Earned on order {order_id}",
        "created_at":   now,
    })

    coin_wallets_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"coin_balance": coins, "total_earned": coins},
         "$set": {"last_updated": now}},
        upsert=True,
    )
    return coins


def debit_coins(user_id: str, order_id: str, coins_to_redeem: float,
                coin_to_inr: float) -> float:
    """
    Debit coins from the dealer's wallet, write a DEBIT transaction.
    Returns the INR discount amount applied (coins * coin_to_inr).
    Raises HTTPException if insufficient balance.
    """
    wallet = get_wallet(user_id)
    balance = wallet.get("coin_balance", 0.0)

    if coins_to_redeem > balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient coin balance. You have {balance:.2f} coins."
        )

    inr_discount = round(coins_to_redeem * coin_to_inr, 2)
    now = utils.get_current_time()
    txn_id = utils.generate_custom_id("CTXN", coin_transactions_collection, "txn_id")

    coin_transactions_collection.insert_one({
        "txn_id":       txn_id,
        "user_id":      user_id,
        "txn_type":     "DEBIT",
        "coins":        coins_to_redeem,
        "reference_id": order_id,
        "note":         f"Redeemed on order {order_id} (₹{inr_discount:.2f} off)",
        "created_at":   now,
    })

    coin_wallets_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"coin_balance": -coins_to_redeem, "total_redeemed": coins_to_redeem},
         "$set": {"last_updated": now}},
        upsert=True,
    )
    return inr_discount


# ─────────────────────────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────────────────────────

@router.get("/admin/config", response_model=schemas.CoinConfigResponse)
def get_config(
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Get current global coin-rewards configuration.
    """
    return get_coin_config()


@router.put("/admin/config", response_model=schemas.CoinConfigResponse)
def update_config(
    payload: schemas.CoinConfigUpdate,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Set or update the coin rewards configuration.

    - `earn_rate_percent`: percentage of order total awarded as coins (e.g. `2.0` → 2%)
    - `coin_to_inr`: INR value of 1 coin (e.g. `1.0` → ₹1 per coin)
    - `is_active`: enable / disable the coin system globally
    """
    cfg = get_coin_config()
    update = {}
    if payload.earn_rate_percent is not None:
        if payload.earn_rate_percent < 0 or payload.earn_rate_percent > 100:
            raise HTTPException(status_code=400, detail="earn_rate_percent must be between 0 and 100.")
        update["earn_rate_percent"] = payload.earn_rate_percent
    if payload.coin_to_inr is not None:
        if payload.coin_to_inr <= 0:
            raise HTTPException(status_code=400, detail="coin_to_inr must be greater than 0.")
        update["coin_to_inr"] = payload.coin_to_inr
    if payload.is_active is not None:
        update["is_active"] = payload.is_active

    now = utils.get_current_time()
    update["updated_at"] = now
    update["updated_by"] = current_user["user_id"]

    coin_config_collection.update_one(
        {"key": _CONFIG_KEY}, {"$set": update}, upsert=True
    )
    return get_coin_config()


@router.get("/admin/wallets", response_model=List[schemas.CoinWalletResponse])
def list_all_wallets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — List coin wallets for all dealers.
    """
    wallets = list(coin_wallets_collection.find().sort("coin_balance", -1).skip(skip).limit(limit))
    for w in wallets:
        w.pop("_id", None)
    return wallets


@router.get("/admin/wallets/{user_id}", response_model=schemas.CoinWalletResponse)
def get_dealer_wallet(
    user_id: str,
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Get a specific dealer's coin wallet.
    """
    return get_wallet(user_id)


@router.get("/admin/transactions", response_model=List[schemas.CoinTransactionResponse])
def list_all_transactions(
    user_id: Optional[str] = Query(None, description="Filter by dealer user_id"),
    txn_type: Optional[str] = Query(None, description="CREDIT or DEBIT"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — List all coin transactions with optional filters.
    """
    query: dict = {}
    if user_id:
        query["user_id"] = user_id
    if txn_type:
        query["txn_type"] = txn_type.upper()

    txns = list(
        coin_transactions_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    for t in txns:
        t.pop("_id", None)
    return txns


@router.post("/admin/adjust/{user_id}", response_model=schemas.CoinWalletResponse)
def admin_adjust_coins(
    user_id: str,
    coins: float,
    note: Optional[str] = Query(None),
    current_user: dict = Depends(auth.RoleChecker(ADMIN_ROLES))
):
    """
    **Admin** — Manually credit (positive) or debit (negative) coins for a dealer.
    Useful for corrections or promotional grants.
    """
    if coins == 0:
        raise HTTPException(status_code=400, detail="coins value cannot be zero.")

    dealer = users_collection.find_one({"user_id": user_id, "role": "Dealer"})
    if not dealer:
        raise HTTPException(status_code=404, detail=f"Dealer '{user_id}' not found.")

    if coins < 0:
        wallet = get_wallet(user_id)
        if wallet["coin_balance"] + coins < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot debit {abs(coins):.2f} coins — current balance is {wallet['coin_balance']:.2f}."
            )

    now = utils.get_current_time()
    txn_id = utils.generate_custom_id("CTXN", coin_transactions_collection, "txn_id")
    txn_type = "CREDIT" if coins > 0 else "DEBIT"
    abs_coins = abs(coins)

    coin_transactions_collection.insert_one({
        "txn_id":       txn_id,
        "user_id":      user_id,
        "txn_type":     txn_type,
        "coins":        abs_coins,
        "reference_id": None,
        "note":         note or f"Manual adjustment by admin {current_user['user_id']}",
        "created_at":   now,
    })

    inc_fields = {"coin_balance": coins}
    if coins > 0:
        inc_fields["total_earned"] = abs_coins
    else:
        inc_fields["total_redeemed"] = abs_coins

    coin_wallets_collection.update_one(
        {"user_id": user_id},
        {"$inc": inc_fields, "$set": {"last_updated": now}},
        upsert=True,
    )
    return get_wallet(user_id)


# ─────────────────────────────────────────────────────────────────
# DEALER ROUTES
# ─────────────────────────────────────────────────────────────────

@router.get("/my-wallet", response_model=schemas.CoinWalletResponse)
def my_wallet(current_user: dict = Depends(auth.RoleChecker(DEALER_ROLES))):
    """
    **Dealer** — Get own coin wallet balance.
    """
    return get_wallet(current_user["user_id"])


@router.get("/my-transactions", response_model=List[schemas.CoinTransactionResponse])
def my_transactions(
    txn_type: Optional[str] = Query(None, description="CREDIT or DEBIT"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(auth.RoleChecker(DEALER_ROLES))
):
    """
    **Dealer** — Get own coin transaction history (credits & debits), newest first.
    """
    query: dict = {"user_id": current_user["user_id"]}
    if txn_type:
        query["txn_type"] = txn_type.upper()

    txns = list(
        coin_transactions_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    for t in txns:
        t.pop("_id", None)
    return txns


@router.get("/config", response_model=schemas.CoinConfigResponse)
def get_public_config():
    """
    **Public / Dealer** — Get current earn-rate config so the frontend can show
    how many coins will be earned on the current cart.
    """
    return get_coin_config()
