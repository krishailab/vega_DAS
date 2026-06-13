import sys
import os

sys.path.append("/Users/hawk/Downloads/vega_traceability_backend")

from app.database import b2b_orders_collection
from app import schemas
from app.api.b2b_order_api import B2BOrderOperations

print("--- Starting Order Payment Status Update unit test ---")

# Setup a dummy order in database for testing
dummy_order = {
    "order_id": "TEST-ORD-999",
    "user_id": "TEST-DEALER-01",
    "total_price": 500.0,
    "payment_status": "Unpaid",
    "status": "Pending",
    "company_address": {
        "business_name": "Test Dealer",
        "address_line": "123 Test St",
        "city": "Vancouver",
        "state": "BC",
        "pincode": "V6B 1A2"
    },
    "items": [],
    "total_items": 0
}

b2b_orders_collection.delete_many({"order_id": "TEST-ORD-999"})
b2b_orders_collection.insert_one(dummy_order)

# 1. Update Payment Status to Paid
payload = schemas.B2BOrderPaymentStatusUpdate(payment_status="Paid")
updated = B2BOrderOperations.update_payment_status("TEST-ORD-999", payload)

print("1. Updated order payment status successfully:")
print("Payment Status:", updated["payment_status"])
assert updated["payment_status"] == "Paid"

# 2. Prevent invalid payment status value
try:
    invalid_payload = schemas.B2BOrderPaymentStatusUpdate(payment_status="InvalidStatus")
    print("Error: Invalid payment status validation failed!")
    sys.exit(1)
except Exception as e:
    print("2. Correctly prevented invalid payment status:", str(e))

# Clean up
b2b_orders_collection.delete_many({"order_id": "TEST-ORD-999"})
print("\n--- All payment status tests passed successfully! ---")
