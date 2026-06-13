"""
Migration: Assign Plant to all Master Admins and Sub-Users
==========================================================
This script assigns a plant (plant_id, plant_name, plant_address) to all
existing Master Admin, Scanner, Inspector and Linker users who currently
have no plant_id set.

Usage:
    PYTHONPATH=. venv/bin/python3 scripts/assign_plant_to_users.py
"""

import os
import sys
import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

ROLES_TO_UPDATE = ["Master Admin", "Scanner", "Inspector", "Linker"]


def migrate():
    print("Connecting to MongoDB...")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    client = MongoClient(mongo_url, tlsCAFile=certifi.where())
    db = client["vega_track"]
    users_col = db["users"]
    plants_col = db["plants"]

    # ── 1. Load available plants ──────────────────────────────────────────────
    plants = list(plants_col.find({}))
    if not plants:
        print("\n❌  No plants found in the database.")
        print("    Please create at least one plant first via the API:")
        print("    POST /api/plants/  {\"plant_name\": \"...\", \"plant_address\": \"...\"}")
        sys.exit(1)

    print(f"\n{'─'*55}")
    print(f"  {'#':<4} {'Plant ID':<20} {'Name'}")
    print(f"{'─'*55}")
    for i, p in enumerate(plants, 1):
        print(f"  {i:<4} {p['plant_id']:<20} {p.get('plant_name', 'N/A')}")
    print(f"{'─'*55}\n")

    # ── 2. Choose plant ───────────────────────────────────────────────────────
    if len(plants) == 1:
        chosen = plants[0]
        print(f"Only one plant found. Auto-selecting: "
              f"{chosen['plant_name']} ({chosen['plant_id']})")
    else:
        while True:
            try:
                choice = int(input(f"Enter plant number to assign [1-{len(plants)}]: "))
                if 1 <= choice <= len(plants):
                    chosen = plants[choice - 1]
                    break
                print(f"  Please enter a number between 1 and {len(plants)}.")
            except ValueError:
                print("  Invalid input. Please enter a number.")

    plant_id      = chosen["plant_id"]
    plant_name    = chosen.get("plant_name", "")
    plant_address = chosen.get("plant_address", "")

    print(f"\nAssigning plant: {plant_name} | {plant_address} | ID: {plant_id}")

    # ── 3. Find users that need updating ──────────────────────────────────────
    query = {
        "role": {"$in": ROLES_TO_UPDATE},
        "$or": [
            {"plant_id": {"$exists": False}},
            {"plant_id": None},
            {"plant_id": ""},
        ]
    }
    users_to_update = list(users_col.find(query))
    print(f"\nFound {len(users_to_update)} user(s) without a plant assignment.")

    if not users_to_update:
        print("✓ Nothing to do — all target users already have a plant assigned.")
        return

    # ── 4. Apply update ───────────────────────────────────────────────────────
    updated = 0
    skipped = 0
    for user in users_to_update:
        uid   = user["user_id"]
        role  = user.get("role", "?")
        name  = f"{user.get('first_name','')} {user.get('last_name','')}".strip()

        res = users_col.update_one(
            {"user_id": uid},
            {"$set": {
                "plant_id":      plant_id,
                "plant_name":    plant_name,
                "plant_address": plant_address,
            }}
        )
        if res.modified_count > 0:
            updated += 1
            print(f"  ✓ [{role}] {name} ({uid})")
        else:
            skipped += 1
            print(f"  - [{role}] {name} ({uid})  (no change)")

    # ── 5. Summary ────────────────────────────────────────────────────────────
    print(f"\n{'─'*55}")
    print(f"  Plant assigned  : {plant_name}")
    print(f"  Users updated   : {updated}")
    print(f"  Users skipped   : {skipped}")
    print(f"{'─'*55}")
    print("✓ Migration complete!\n")


if __name__ == "__main__":
    migrate()
