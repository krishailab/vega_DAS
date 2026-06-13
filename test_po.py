import os
import sys

from app.po_generator import generate_po_pdf

order_data = {
    "order_id": "B2B-ORD0001",
    "created_at": "2026-05-25",
    "payment_type": "credit",
    "subtotal": 4800.0,
    "discount_applied": 0.0,
    "total_price": 4800.0,
    "items": [
        {
            "sku_no": "VG-BLT-BLK-L",
            "name": "Vega Bolt Full Face Helmet - Black - L",
            "quantity": 100,
            "dealer_price": 42.0,
            "subtotal": 4200.0
        },
        {
            "sku_no": "VG-GLV-001",
            "name": "Riding Gloves",
            "quantity": 50,
            "dealer_price": 12.0,
            "subtotal": 600.0
        }
    ],
    "company_address": {
        "address_line": "123 Test St",
        "city": "Vancouver",
        "state": "BC",
        "pincode": "V6B 1A2",
        "gstin": "987654321"
    }
}

user_data = {
    "business_name": "ABC Powersports",
    "mobile": "604-555-0145",
    "email": "test@test.com"
}

buffer = generate_po_pdf(order_data, user_data)
with open("test_po_output.pdf", "wb") as f:
    f.write(buffer.read())
print("Created test_po_output.pdf successfully!")
