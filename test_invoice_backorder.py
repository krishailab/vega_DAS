import sys
import os
from datetime import datetime
from fastapi import HTTPException

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import (
    b2b_orders_collection,
    b2b_invoices_collection,
    b2b_inward_products_collection,
    b2b_gst_settings_collection,
    users_collection
)
from app import schemas
from app.api.b2b_order_api import B2BOrderOperations
from app.api.b2b_admin_api import B2BGstSettingsOperations
from app.invoice_generator import generate_invoice_pdf

def test_invoice_and_backorders():
    print("--- Starting Invoice & Backorder Logic unit tests ---")
    
    # 1. Setup clean data in B2B inward catalog (Stock)
    b2b_inward_products_collection.delete_many({"variant_id": "TEST-VAR-101"})
    b2b_inward_products_collection.insert_one({
        "inward_id": "INW-TEST-101",
        "variant_id": "TEST-VAR-101",
        "sku_no": "VG-HELMET-M",
        "dealer_price": 100.0,
        "quantity": 6, # ONLY 6 IN STOCK!
        "is_active": True
    })
    
    # 2. Configure GST/HST rate for Ontario (ON)
    b2b_gst_settings_collection.delete_many({"state": "ON"})
    b2b_gst_settings_collection.insert_one({
        "setting_id": "GSTS-ON",
        "state": "ON",
        "tax_type": "HST",
        "percent": 13.0,
        "created_by": "SYSTEM",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })

    # 3. Create a mock dealer profile
    users_collection.delete_many({"user_id": "DL-TEST-99"})
    dealer_user = {
        "user_id": "DL-TEST-99",
        "first_name": "Ontario",
        "last_name": "Powersports",
        "business_name": "Ontario Powersports",
        "role": "Dealer",
        "mobile_number": "416-555-9999",
        "email": "dealer@ontario.ca"
    }
    users_collection.insert_one(dealer_user)

    # 4. Construct B2B order with 10 units of VG-HELMET-M (exceeds stock of 6)
    b2b_orders_collection.delete_many({"order_id": "ORD-TEST-999"})
    b2b_invoices_collection.delete_many({"order_id": {"$in": ["ORD-TEST-999", "ORD-TEST-PREVIEW", "ORD-TEST-MANUAL"]}})
    order_doc = {
        "order_id": "ORD-TEST-999",
        "user_id": "DL-TEST-99",
        "company_address": {
            "business_name": "Ontario Powersports",
            "address_line": "456 Queen St",
            "city": "Toronto",
            "state": "ON",
            "pincode": "M5V 2A2"
        },
        "shipping_address": {
            "business_name": "Ontario Powersports",
            "address_line": "456 Queen St",
            "city": "Toronto",
            "state": "ON",
            "pincode": "M5V 2A2"
        },
        "items": [
            {
                "inward_id": "INW-TEST-101",
                "variant_id": "TEST-VAR-101",
                "sku_no": "VG-HELMET-M",
                "name": "Vega Helmets Full Face M",
                "quantity": 10, # Ordered 10
                "dealer_price": 100.0,
                "subtotal": 1000.0,
                "quantity_invoiced": 0,
                "quantity_backordered": 10
            }
        ],
        "total_items": 10,
        "subtotal": 1000.0,
        "total_price": 1000.0,
        "status": "Pending",
        "payment_status": "Unpaid",
        "invoices": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    b2b_orders_collection.insert_one(order_doc)
    
    # 5. Generate first invoice (should invoice 6, backorder 4)
    print("Generating first invoice...")
    inv1 = B2BOrderOperations.generate_invoice("ORD-TEST-999", "SYS-ADMIN")
    print("Invoice 1 details:")
    print(inv1)
    
    assert inv1["invoice_id"] == "ORD-TEST-999-INV-01"
    assert len(inv1["items"]) == 1
    assert inv1["items"][0]["quantity"] == 6 # Fulfilled available stock
    assert inv1["subtotal"] == 600.0 # 6 * 100
    assert inv1["tax_type"] == "HST"
    assert inv1["tax_rate"] == 13.0
    assert inv1["tax_amount"] == 78.0 # 13% of 600
    assert inv1["total_with_tax"] == 678.0
    
    # Verify stock is now 0
    inward = b2b_inward_products_collection.find_one({"inward_id": "INW-TEST-101"})
    print("Stock remaining in catalog:", inward["quantity"])
    assert inward["quantity"] == 0
    
    # Verify order item state
    order = B2BOrderOperations.get_order("ORD-TEST-999", "DL-TEST-99", "Dealer")
    print("Order details after first invoice:")
    item = order["items"][0]
    print(f"Invoiced: {item['quantity_invoiced']}, Backordered: {item['quantity_backordered']}, has_backorder: {order['has_backorder']}")
    assert item["quantity_invoiced"] == 6
    assert item["quantity_backordered"] == 4
    assert order["has_backorder"] is True
    
    # Verify dashboard backorder count
    from app.api.b2b_dashboard_api import B2BDashboardOperations as DashOps
    summary = DashOps.get_sales_summary()
    print("Dashboard backorder orders count:", summary.backorder_orders)
    assert summary.backorder_orders == 1
    
    # 6. Restock item (add 10 units to stock)
    print("Restocking 10 units...")
    b2b_inward_products_collection.update_one(
        {"inward_id": "INW-TEST-101"},
        {"$set": {"quantity": 10}}
    )
    
    # 7. Generate second invoice (should fulfill remaining 4 backordered units)
    print("Generating second invoice...")
    inv2 = B2BOrderOperations.generate_invoice("ORD-TEST-999", "SYS-ADMIN")
    print("Invoice 2 details:")
    print(inv2)
    
    assert inv2["invoice_id"] == "ORD-TEST-999-INV-02"
    assert inv2["items"][0]["quantity"] == 4 # Fulfills the remaining 4 units
    assert inv2["subtotal"] == 400.0
    assert inv2["tax_amount"] == 52.0
    assert inv2["total_with_tax"] == 452.0
    
    # Verify stock is now 6 (10 - 4)
    inward = b2b_inward_products_collection.find_one({"inward_id": "INW-TEST-101"})
    assert inward["quantity"] == 6
    
    # Verify order item state (fully fulfilled, no backorder)
    order = B2BOrderOperations.get_order("ORD-TEST-999", "DL-TEST-99", "Dealer")
    item = order["items"][0]
    print("Order details after second invoice:")
    print(f"Invoiced: {item['quantity_invoiced']}, Backordered: {item['quantity_backordered']}, has_backorder: {order['has_backorder']}")
    assert item["quantity_invoiced"] == 10
    assert item["quantity_backordered"] == 0
    assert order["has_backorder"] is False

    # Verify dashboard count is now 0
    summary_after = DashOps.get_sales_summary()
    print("Dashboard backorder orders count after fulfillment:", summary_after.backorder_orders)
    assert summary_after.backorder_orders == 0
    
    # 8. Test PDF generation (Invoice 2)
    print("Testing PDF Generation...")
    pdf_buffer = generate_invoice_pdf(order, inv2, dealer_user)
    assert pdf_buffer is not None
    assert len(pdf_buffer.getvalue()) > 0
    
    # Save PDF locally for manual review if needed
    with open("test_invoice_output.pdf", "wb") as f:
        f.write(pdf_buffer.read())
    print("Saved test PDF to 'test_invoice_output.pdf'.")

    # 9. Test Default GST Fallback & Invoice Preview
    print("Testing Default GST Fallback and Invoice Preview...")
    b2b_gst_settings_collection.delete_many({"is_default": True})
    b2b_gst_settings_collection.insert_one({
        "setting_id": "GSTS-DEFAULT",
        "state": "Default Canada",
        "tax_type": "GST",
        "percent": 10.0,
        "is_default": True,
        "created_by": "SYSTEM",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })
    
    b2b_orders_collection.delete_many({"order_id": "ORD-TEST-PREVIEW"})
    preview_order = {
        "order_id": "ORD-TEST-PREVIEW",
        "user_id": "DL-TEST-99",
        "shipping_address": {"state": "XX"}, # Unknown state
        "items": [
            {
                "inward_id": "INW-TEST-101",
                "variant_id": "TEST-VAR-101",
                "sku_no": "VG-HELMET-M",
                "name": "Vega Helmets M",
                "quantity": 5,
                "dealer_price": 100.0,
                "subtotal": 500.0,
                "quantity_invoiced": 0,
                "quantity_backordered": 5
            }
        ],
        "total_items": 5,
        "subtotal": 500.0,
        "total_price": 500.0,
        "status": "Pending",
        "invoices": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    b2b_orders_collection.insert_one(preview_order)
    
    b2b_inward_products_collection.update_one(
        {"inward_id": "INW-TEST-101"},
        {"$set": {"quantity": 3}}
    )
    
    preview = B2BOrderOperations.preview_invoice("ORD-TEST-PREVIEW")
    print("Preview invoice details:")
    print(preview)
    
    assert len(preview["items_to_invoice"]) == 1
    assert preview["items_to_invoice"][0]["quantity"] == 3
    assert preview["subtotal"] == 300.0
    assert preview["tax_type"] == "GST"
    assert preview["tax_rate"] == 10.0 # Fell back to default GST
    assert preview["tax_amount"] == 30.0 # 10% of 300
    assert preview["total_with_tax"] == 330.0
    
    inward_check = b2b_inward_products_collection.find_one({"inward_id": "INW-TEST-101"})
    assert inward_check["quantity"] == 3
    
    order_check = b2b_orders_collection.find_one({"order_id": "ORD-TEST-PREVIEW"})
    assert len(order_check.get("invoices", [])) == 0
    print("Invoice Preview does not modify database state: Verified.")

    # Compile simulated preview PDF to verify ReportLab drawing callback
    sim_inv = {
        "invoice_id": "ORD-TEST-PREVIEW",
        "items": preview["items_to_invoice"],
        "subtotal": preview["subtotal"],
        "tax_type": preview["tax_type"],
        "tax_rate": preview["tax_rate"],
        "tax_amount": preview["tax_amount"],
        "total_with_tax": preview["total_with_tax"],
        "created_at": datetime.now()
    }
    pdf_preview_buffer = generate_invoice_pdf(preview_order, sim_inv, dealer_user, is_preview=True)
    assert pdf_preview_buffer is not None
    assert len(pdf_preview_buffer.getvalue()) > 0
    with open("test_invoice_preview_output.pdf", "wb") as f:
        f.write(pdf_preview_buffer.read())
    print("Saved preview PDF to 'test_invoice_preview_output.pdf'.")
    
    b2b_orders_collection.delete_many({"order_id": "ORD-TEST-PREVIEW"})
    b2b_gst_settings_collection.delete_many({"setting_id": "GSTS-DEFAULT"})

    # 10. Test Manual Quantity Overrides
    print("Testing Manual Quantity Overrides...")
    b2b_gst_settings_collection.insert_one({
        "setting_id": "GSTS-DEFAULT",
        "state": "Default Canada",
        "tax_type": "GST",
        "percent": 10.0,
        "is_default": True,
        "created_by": "SYSTEM",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })

    b2b_orders_collection.delete_many({"order_id": "ORD-TEST-MANUAL"})
    manual_order = {
        "order_id": "ORD-TEST-MANUAL",
        "user_id": "DL-TEST-99",
        "shipping_address": {"state": "XX"},
        "items": [
            {
                "inward_id": "INW-TEST-101",
                "variant_id": "TEST-VAR-101",
                "sku_no": "VG-HELMET-M",
                "name": "Vega Helmets M",
                "quantity": 5,
                "dealer_price": 100.0,
                "subtotal": 500.0,
                "quantity_invoiced": 0,
                "quantity_backordered": 5
            }
        ],
        "total_items": 5,
        "subtotal": 500.0,
        "total_price": 500.0,
        "status": "Pending",
        "invoices": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    b2b_orders_collection.insert_one(manual_order)

    # Set stock to 3
    b2b_inward_products_collection.update_one(
        {"inward_id": "INW-TEST-101"},
        {"$set": {"quantity": 3}}
    )

    from app.schemas import B2BInvoiceManualRequest, B2BInvoiceManualItem

    # A. Preview manual override with 2 units (valid: <= stock 3, <= backorder 5)
    payload_valid = B2BInvoiceManualRequest(items=[B2BInvoiceManualItem(inward_id="INW-TEST-101", quantity=2)])
    preview_manual = B2BOrderOperations.preview_invoice("ORD-TEST-MANUAL", payload_valid)
    assert len(preview_manual["items_to_invoice"]) == 1
    assert preview_manual["items_to_invoice"][0]["quantity"] == 2
    assert preview_manual["subtotal"] == 200.0
    assert preview_manual["total_with_tax"] == 220.0

    # B. Preview manual override with 4 units (invalid: > stock 3)
    payload_exceed_stock = B2BInvoiceManualRequest(items=[B2BInvoiceManualItem(inward_id="INW-TEST-101", quantity=4)])
    try:
        B2BOrderOperations.preview_invoice("ORD-TEST-MANUAL", payload_exceed_stock)
        assert False, "Should have failed as quantity exceeds stock"
    except HTTPException as e:
        assert e.status_code == 400
        assert "available in stock" in e.detail

    # C. Preview manual override with 6 units (invalid: > backordered 5)
    payload_exceed_backorder = B2BInvoiceManualRequest(items=[B2BInvoiceManualItem(inward_id="INW-TEST-101", quantity=6)])
    try:
        B2BOrderOperations.preview_invoice("ORD-TEST-MANUAL", payload_exceed_backorder)
        assert False, "Should have failed as quantity exceeds backorder"
    except HTTPException as e:
        assert e.status_code == 400
        assert "pending backorder" in e.detail

    # D. Generate invoice with manual override of 2 units
    inv_manual = B2BOrderOperations.generate_invoice("ORD-TEST-MANUAL", "SYSTEM", payload_valid)
    assert inv_manual["subtotal"] == 200.0
    assert len(inv_manual["items"]) == 1
    assert inv_manual["items"][0]["quantity"] == 2

    # Verify stock deducted: 3 - 2 = 1
    inward_check = b2b_inward_products_collection.find_one({"inward_id": "INW-TEST-101"})
    assert inward_check["quantity"] == 1

    # Verify order updated: quantity_invoiced = 2, quantity_backordered = 3
    order_check = B2BOrderOperations.get_order("ORD-TEST-MANUAL", "DL-TEST-99", "Dealer")
    assert order_check["items"][0]["quantity_invoiced"] == 2
    assert order_check["items"][0]["quantity_backordered"] == 3
    assert len(order_check["invoices"]) == 1

    b2b_orders_collection.delete_many({"order_id": "ORD-TEST-MANUAL"})
    b2b_gst_settings_collection.delete_many({"setting_id": "GSTS-DEFAULT"})
    print("Testing Manual Quantity Overrides: Verified.")
    
    # Clean up
    b2b_inward_products_collection.delete_many({"variant_id": "TEST-VAR-101"})
    b2b_gst_settings_collection.delete_many({"state": "ON"})
    users_collection.delete_many({"user_id": "DL-TEST-99"})
    b2b_orders_collection.delete_many({"order_id": "ORD-TEST-999"})
    b2b_invoices_collection.delete_many({"order_id": {"$in": ["ORD-TEST-999", "ORD-TEST-PREVIEW", "ORD-TEST-MANUAL"]}})
    
    # Re-initialize original Ontario GST setting from populator
    from init_gst_settings import init_gst_settings
    init_gst_settings()
    
    print("\n--- All invoice and backorder tests passed successfully! ---")

if __name__ == "__main__":
    test_invoice_and_backorders()
