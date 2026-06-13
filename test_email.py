import os
import sys

from app.po_generator import generate_po_pdf
from app.email_sender import send_po_email

order_data = {
    "order_id": "B2B-ORD26AAAA0005",
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

print("Generating PDF...")
pdf_buffer = generate_po_pdf(order_data, user_data)

target_email = "bhagatkrish65@gmail.com"
print(f"Sending test email to {target_email}...")

send_po_email(
    to_email=target_email,
    subject=f"TEST: Purchase Order Confirmation - {order_data['order_id']}",
    body=f"Dear {user_data['business_name']},\n\nThis is a test email from the Vega System. Please find the attached PDF.\n\nThank you,\nVega Auto Accessories Ltd.",
    pdf_buffer=pdf_buffer,
    filename=f"PO_{order_data['order_id']}.pdf"
)

print("Done!")
