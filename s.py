"""
seed_dealer_addresses.py
────────────────────────
Seed multiple company addresses of different types (shipping, billing, business)
for a B2B Dealer by calling the live FastAPI backend.

Usage:
    python scratch/seed_dealer_addresses.py

Configure the variables in the CONFIG block below before running.
"""

import requests
import json

# ═══════════════════════════════════════════════════════════════
#  CONFIG — edit these before running
# ═══════════════════════════════════════════════════════════════
BASE_URL   = "http://127.0.0.1:8000"   # Local dev server
EMAIL      = "7067954499"       # Dealer login email
PASSWORD   = "123"       # Dealer password
# ═══════════════════════════════════════════════════════════════

ADDRESSES = [
    # ── 1. Billing Address ───────────────────────────────────────
    {
        "business_name": "Acme Motors Pvt Ltd",
        "address_line": "12, Finance Tower, MG Road",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
        "address_type": "billing",
        "is_business_address": False,
        "gstin": "29AABCA1234A1Z5",
        "business_email": "billing@acmemotors.in",
        "business_mobile": "08044332211",
        "alternate_mobile": None,
        "web": "https://acmemotors.in",
    },
    # ── 2. Shipping Address ──────────────────────────────────────
    {
        "business_name": "Acme Motors — Warehouse",
        "address_line": "Plot 7, Industrial Estate, Phase II",
        "city": "Pune",
        "state": "Maharashtra",
        "pincode": "411019",
        "address_type": "shipping",
        "is_business_address": False,
        "gstin": None,
        "business_email": "warehouse@acmemotors.in",
        "business_mobile": "02044332211",
        "alternate_mobile": "9876543210",
        "web": None
    },
    # ── 3. Second Billing Address (branch office) ────────────────
    {
        "business_name": "Acme Motors — Delhi Branch",
        "address_line": "301, Connaught Place",
        "city": "New Delhi",
        "state": "Delhi",
        "pincode": "110001",
        "address_type": "billing",
        "is_business_address": False,
        "gstin": "07AABCA1234A1Z3",
        "business_email": "delhi@acmemotors.in",
        "business_mobile": "01144332211",
        "alternate_mobile": None,
        "web": None,
    },
    # ── 4. Another Shipping Address ──────────────────────────────
    {
        "business_name": "Acme Motors — Chennai Depot",
        "address_line": "44, Anna Salai, Guindy",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "pincode": "600032",
        "address_type": "shipping",
        "is_business_address": False,
        "gstin": None,
        "business_email": "chennai@acmemotors.in",
        "business_mobile": "04444332211",
        "alternate_mobile": None,
        "web": None,
    },
]


def login(session: requests.Session) -> str:
    """Authenticate and return Bearer token."""
    print(f"🔐  Logging in as {EMAIL} ...")
    resp = session.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code != 200:
        raise SystemExit(f"❌  Login failed ({resp.status_code}): {resp.text}")

    token = resp.json().get("access_token")
    if not token:
        raise SystemExit(f"❌  No access_token in response: {resp.text}")

    print("✅  Logged in successfully.\n")
    return token


def add_address(session: requests.Session, payload: dict, token: str) -> dict:
    """POST a single address and return the response dict."""
    resp = session.post(
        f"{BASE_URL}/api/v1/b2b-dealer/company/addresses",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


def list_addresses(session: requests.Session, token: str):
    """GET and print all addresses currently on the dealer profile."""
    resp = session.get(
        f"{BASE_URL}/api/v1/b2b-dealer/company/addresses",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        addrs = resp.json()
        print(f"\n📋  Current addresses on profile ({len(addrs)} total):")
        for a in addrs:
            tag = "⚑ BUSINESS" if a.get("is_business_address") else a.get("address_type", "unknown").upper()
            print(f"   [{tag}]  {a.get('business_name')} — {a.get('city')}, {a.get('state')}  (ID: {a.get('address_id')})")
    else:
        print(f"⚠️   Could not fetch addresses: {resp.status_code} {resp.text}")


def main():
    print("=" * 60)
    print("  Vega Track — Seed B2B Dealer Addresses")
    print("=" * 60)

    session = requests.Session()
    token = login(session)

    print(f"📦  Seeding {len(ADDRESSES)} address(es)...\n")
    for idx, addr in enumerate(ADDRESSES, 1):
        label = f"[{addr['address_type'].upper()}] {addr['business_name']}"
        print(f"  ({idx}/{len(ADDRESSES)}) Adding {label} ...")
        resp = add_address(session, addr, token)
        if resp.status_code in (200, 201):
            created = resp.json()
            print(f"   ✅  Done — Address ID: {created.get('address_id')}")
        else:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            print(f"   ❌  Failed ({resp.status_code}): {body}")

    list_addresses(session, token)
    print("\n✅  Seeding complete.")


if __name__ == "__main__":
    main()
