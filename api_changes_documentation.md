# Vega Traceability Backend — Full API Changes & New Features Documentation

> Last Updated: 2026-06-07  
> Covers all changes made from initial commit up to the latest session.

---

## Table of Contents

1. [Multi-Currency MRP on Product Variants](#1-multi-currency-mrp-on-product-variants)
2. [B2B Inward — Currency Selection](#2-b2b-inward--currency-selection)
3. [Job Card — Currency Field](#3-job-card--currency-field)
4. [Label Print PDF — Dynamic Currency & MRP](#4-label-print-pdf--dynamic-currency--mrp)
5. [B2B Cart — Currency-Aware MRP Resolution](#5-b2b-cart--currency-aware-mrp-resolution)
6. [B2B Inward Cards — Currency-Aware MRP Resolution](#6-b2b-inward-cards--currency-aware-mrp-resolution)
7. [B2B Orders — Backorder & Invoice System](#7-b2b-orders--backorder--invoice-system)
8. [Invoice PDF Generation](#8-invoice-pdf-generation)
9. [Address-Based GST/HST Tax Settings](#9-address-based-gsthst-tax-settings)
10. [Packaging Details on Product Submodels](#10-packaging-details-on-product-submodels)
11. [Schema Changes Summary](#11-schema-changes-summary)
12. [B2B Submodel-Centric API Refactor](#12-b2b-submodel-centric-api-refactor)

---

## 1. Multi-Currency MRP on Product Variants

### What Changed
`mrp` on a product variant was previously a single `float`. It is now stored as a **dynamic dictionary** mapping currency codes to amounts:

```json
{
  "INR": 1850.0,
  "USD": 25.0,
  "CAD": 30.0
}
```

### Endpoints Affected

#### `POST /api/v1/product-master/variants/` — Create Product Variant
**Form Field:**
| Field | Type | Description |
|-------|------|-------------|
| `mrp` | `str` (JSON) | JSON string of currency→amount map or a plain float for INR fallback |

**Examples:**
```
# Multi-currency
mrp = '{"INR": 1850.0, "USD": 25.0, "CAD": 30.0}'

# Legacy single value (auto-wrapped as INR)
mrp = '1850'
```

**Response (variant object):**
```json
{
  "variant_id": "PVAR26AAAA0001",
  "sku_no": "VEGA-BOLT-M-RED",
  "mrp": {
    "INR": 1850.0,
    "USD": 25.0,
    "CAD": 30.0
  },
  "color": "Red",
  "size": 58
}
```

---

#### `PUT /api/v1/product-master/variants/{variant_id}` — Update Product Variant
**Form Field:**
| Field | Type | Description |
|-------|------|-------------|
| `mrp` | `str` (JSON) | JSON string of currency→amount map or plain float |

**Response:** Same as Create above.

---

## 2. B2B Inward — Currency Selection

### What Changed
When inwarding a product into the B2B catalog, you now **select the currency** the inward price and MRP will be quoted in.

### Endpoint

#### `POST /api/v1/b2b-admin/inwards/` — Create B2B Inward
**Request Body:**
```json
{
  "variant_id": "PVAR26AAAA0001",
  "dealer_price": 20.0,
  "currency": "USD",
  "quantity": 150,
  "reference_no": "REF-2026-001",
  "is_individual": true,
  "is_carton": false,
  "is_featured": false,
  "is_new_arrival": true,
  "is_best_seller": false,
  "is_active": true
}
```

**Supported Currencies:** `INR`, `USD`, `CAD`

**Response:**
```json
{
  "inward_id": "B2B-INW26AAAA0001",
  "variant_id": "PVAR26AAAA0001",
  "sku_no": "VEGA-BOLT-M-RED",
  "dealer_price": 20.0,
  "currency": "USD",
  "quantity": 150,
  "reference_no": "REF-2026-001",
  "is_individual": true,
  "is_carton": false,
  "is_featured": false,
  "is_new_arrival": true,
  "is_best_seller": false,
  "is_active": true,
  "created_by": "USR26AAAA0001",
  "created_at": "2026-06-07T00:00:00",
  "updated_at": "2026-06-07T00:00:00"
}
```

---

#### `PUT /api/v1/b2b-admin/inwards/{inward_id}` — Update B2B Inward
**Request Body (all fields optional):**
```json
{
  "dealer_price": 22.0,
  "currency": "CAD",
  "quantity": 200,
  "is_active": true
}
```

---

## 3. Job Card — Currency Field

### What Changed
Job cards now carry a `currency` field that determines which currency's MRP is shown on the printed label.

### Endpoint

#### `POST /job-cards/assemble` — Create Assemble Job Card
**Request Body:**
```json
{
  "job_card": {
    "jobcard_date": "2026-06-07",
    "part_composition": "Fiber Glass Shell",
    "quantity": 250,
    "station_ids": ["STN26AAAA0001"],
    "product_model_name": "BOLT",
    "currency": "CAD"
  },
  "variant_sku": "VEGA-BOLT-M-RED"
}
```

**Fields:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `currency` | `str` | `"INR"` | One of `INR`, `USD`, `CAD` |

**Response includes the currency field:**
```json
{
  "jobcard_id": "JBC26AAAA0001",
  "jobcard_no": "JC-20260607-0001",
  "currency": "CAD",
  "variant_id": "PVAR26AAAA0001",
  "variant_sku": "VEGA-BOLT-M-RED",
  "mrp": {
    "INR": 1850.0,
    "USD": 25.0,
    "CAD": 30.0
  },
  ...
}
```

---

## 4. Label Print PDF — Dynamic Currency & MRP

### What Changed
The label PDF generator (`/print-labels`) now:
- Reads the `currency` field from the job card
- Looks up the matching MRP amount from the variant's `mrp` dictionary
- Displays the appropriate currency symbol

### Currency → Symbol Mapping

The system dynamically maps ISO 4217 currency codes to their respective symbols using a global lookup (supporting `INR` → `Rs.`, `USD` → `$`, `CAD` → `C$`, `EUR` → `€`, `GBP` → `£`, etc.). If a currency code is not in the common mapping, the uppercase code itself is used as the symbol.

### MRP Resolution Logic (fallback chain)
1. Try `mrp[currency]` (exact match for selected currency)
2. If not found, try `mrp["INR"]` (INR fallback)
3. If not found, use the first value in the dict
4. If `mrp` is a legacy `float`, use it directly

### Label Print Endpoint

#### `GET /job-cards/{jobcard_id}/print-labels`
**Query params:** `start`, `end` (label range)

**PDF Output includes:**
- `MRP   :   C$ 30/-` (or `Rs. 1,850/-`, `$ 25/-`)
- `(INCLUSIVE OF ALL TAXES)` tag line
- EAN-13 barcode with GS1 digits rotated on the right side
- QR code for the unit's central tracking QR ID

---

## 5. B2B Cart — Currency-Aware MRP Resolution

### What Changed
When a dealer views their cart, each line item now includes:
- `currency`: the currency of the inward product
- `mrp`: the resolved float MRP for that currency (from the variant's dict)

### Endpoint

#### `GET /api/v1/b2b-cart/`
**Response:**
```json
{
  "items": [
    {
      "inward_id": "B2B-INW26AAAA0001",
      "variant_id": "PVAR26AAAA0001",
      "sku_no": "VEGA-BOLT-M-RED",
      "name": "Vega Bolt Medium Red",
      "image": "https://cdn.example.com/vega-bolt.jpg",
      "dealer_price": 20.0,
      "currency": "USD",
      "mrp": 25.0,
      "quantity": 5,
      "subtotal": 100.0,
      "is_individual": true,
      "is_carton": false
    }
  ],
  "total_items": 5,
  "total_price": 100.0
}
```

**Note:** `mrp` is the resolved single float for the inward's selected currency (USD → `25.0`), not the full dictionary.

---

## 6. B2B Inward Cards — Currency-Aware MRP Resolution

### Endpoint

#### `GET /api/v1/b2b-admin/inwards/cards`
**Query params:** `is_featured`, `is_new_arrival`, `is_best_seller`, `is_active`, `is_individual`, `is_carton`, `category_id`, `subcategory_id`, `brand_id`, `model_id`, `submodel_id`

**Response (card object):**
```json
{
  "inward_id": "B2B-INW26AAAA0001",
  "variant_id": "PVAR26AAAA0001",
  "sku_no": "VEGA-BOLT-M-RED",
  "name": "Vega Bolt Medium Red",
  "image": "https://cdn.example.com/vega-bolt.jpg",
  "dealer_price": 20.0,
  "currency": "USD",
  "mrp": 25.0,
  "quantity": 150,
  "reference_no": "REF-2026-001",
  "color": "Red",
  "size": 58,
  "size_name": "M",
  "carton_box_size": 6,
  "is_individual": true,
  "is_carton": false,
  "is_featured": false,
  "is_new_arrival": true,
  "is_best_seller": false,
  "is_active": true,
  "category_id": "CAT26AAAA0001",
  "category_name": "HELMETS",
  "brand_name": "VEGA",
  "model_name": "BOLT",
  "submodel_name": "STANDARD"
}
```

---

## 7. B2B Orders — Full Lifecycle

### Overview
The B2B order system manages the complete lifecycle from checkout to invoice delivery.

**Order Statuses:** `Pending` → `Confirmed` → `Processing` → `Dispatched` → `Delivered` → `Cancelled`

**Payment Statuses:** `Unpaid`, `Paid`, `Refunded`

---

### 7.1 Checkout Summary (Preview)

#### `POST /api/v1/b2b-orders/checkout/summary`
Preview the checkout totals — including coupon discounts, coin discounts, and coins to be earned — **without placing the order**.

**Request Body (all optional):**
```json
{
  "address_id": "ADDR26AAAA0001",
  "shipping_address_id": "ADDR26AAAA0002",
  "billing_address_id": "ADDR26AAAA0003",
  "coupon_code": "VEGA10",
  "coins_to_redeem": 50.0
}
```

**Response:**
```json
{
  "company_address": { "address_line": "...", "city": "Bangalore", "state": "Karnataka", "pincode": "560001" },
  "shipping_address": { ... },
  "billing_address": { ... },
  "items": [
    {
      "inward_id": "B2B-INW26AAAA0001",
      "sku_no": "VEGA-BOLT-M-RED",
      "name": "Vega Bolt Medium Red",
      "dealer_price": 20.0,
      "currency": "USD",
      "mrp": 25.0,
      "quantity": 5,
      "subtotal": 100.0
    }
  ],
  "total_items": 5,
  "subtotal": 100.0,
  "discount_applied": 10.0,
  "coin_discount": 5.0,
  "total_price": 85.0,
  "coupon_code": "VEGA10",
  "coin_balance": 200.0,
  "potential_coins_earned": 8.5
}
```

---

### 7.2 Place Order (Checkout)

#### `POST /api/v1/b2b-orders/checkout`
Places the order, clears the cart, awards coins earned, and emails a Purchase Order PDF to the dealer and admin in the background.

**Request Body (all optional):**
```json
{
  "address_id": "ADDR26AAAA0001",
  "shipping_address_id": "ADDR26AAAA0002",
  "billing_address_id": "ADDR26AAAA0003",
  "payment_type": "credit",
  "coupon_code": "VEGA10",
  "coins_to_redeem": 50.0
}
```

**Response:** Full `B2BOrderResponse` object (see §7.4).

**Validations:**
- Order total must not exceed the dealer's `order_credit_limit`
- Sum of outstanding orders + new order must not exceed `overall_credit_limit`
- Cart must not be empty

**Side Effects:**
- Cart is cleared
- Coins are debited if `coins_to_redeem` > 0
- Coins are credited based on `earn_rate_percent` from the coin config
- PO PDF is emailed (background task) to the dealer and admin

---

### 7.3 List Orders

#### `GET /api/v1/b2b-orders/my-orders` _(Dealer)_
Returns the authenticated dealer's own orders.

**Query params:** `status` (filter)

**Response:** `List[B2BOrderSummary]`

---

#### `GET /api/v1/b2b-orders/` _(Admin)_
List all orders with filtering and pagination.

**Query params:**

| Param | Type | Description |
|-------|------|-------------|
| `status` | `str` | Filter by order status |
| `dealer_id` | `str` | Filter by dealer user_id |
| `search` | `str` | Search by order_id, dealer name, or mobile |
| `skip` | `int` | Pagination offset (default `0`) |
| `limit` | `int` | Page size (default `50`, max `200`) |

**Response:**
```json
{
  "orders": [ { ...B2BOrderSummary... } ],
  "total": 120,
  "skip": 0,
  "limit": 50
}
```

---

#### `GET /api/v1/b2b-orders/admin/dealer/{dealer_id}` _(Admin)_
All orders placed by a specific dealer.

---

### 7.4 Get Order Detail

#### `GET /api/v1/b2b-orders/{order_id}`
Returns full order details, including all items (with currency-resolved MRP), all invoices, and current backorder state.

**Response:**
```json
{
  "order_id": "B2BORD26AAAA0001",
  "user_id": "USR26AAAA0001",
  "ordered_by": "John Doe",
  "company_address": { ... },
  "shipping_address": { ... },
  "billing_address": { ... },
  "items": [
    {
      "inward_id": "B2B-INW26AAAA0001",
      "sku_no": "VEGA-BOLT-M-RED",
      "name": "Vega Bolt Medium Red",
      "dealer_price": 20.0,
      "currency": "USD",
      "mrp": 25.0,
      "quantity": 10,
      "quantity_invoiced": 8,
      "quantity_backordered": 2,
      "subtotal": 200.0
    },
    {
      "inward_id": "B2B-INW26AAAA0002",
      "sku_no": "VEGA-EDGE-L-BLK",
      "name": "Vega Edge Large Black",
      "dealer_price": 18.0,
      "currency": "USD",
      "mrp": 22.0,
      "quantity": 5,
      "quantity_invoiced": 0,
      "quantity_backordered": 5,
      "subtotal": 90.0
    }
  ],
  "total_items": 15,
  "subtotal": 290.0,
  "discount_applied": 0.0,
  "coin_discount": 0.0,
  "total_price": 290.0,
  "status": "Confirmed",
  "payment_type": "credit",
  "payment_status": "Unpaid",
  "coupon_code": "",
  "admin_note": null,
  "cancel_reason": null,
  "dispatch_details": null,
  "status_history": [
    { "from": "Pending", "to": "Confirmed", "changed_by": "USR_ADMIN", "changed_at": "...", "note": "Invoice generated" }
  ],
  "invoices": [
    {
      "invoice_id": "B2BORD26AAAA0001-INV-01",
      "items": [
        {
          "inward_id": "B2B-INW26AAAA0001",
          "sku_no": "VEGA-BOLT-M-RED",
          "name": "Vega Bolt Medium Red",
          "quantity": 8,
          "dealer_price": 20.0,
          "subtotal": 160.0
        }
      ],
      "subtotal": 160.0,
      "tax_type": "GST",
      "tax_rate": 18.0,
      "tax_amount": 28.8,
      "total_with_tax": 188.8,
      "created_at": "2026-06-07T00:00:00"
    }
  ],
  "has_backorder": true,
  "coins_earned": 20.0,
  "coins_redeemed": 0.0,
  "dealer_coin_balance": 220.0,
  "po_url": "/api/v1/b2b-orders/B2BORD26AAAA0001/po",
  "tracking_url": null,
  "created_at": "2026-06-07T00:00:00",
  "updated_at": "2026-06-07T00:00:00"
}
```

**Backorder Item Fields Explained:**

| Field | Description |
|-------|-------------|
| `quantity` | Total qty originally ordered |
| `quantity_invoiced` | Qty shipped in issued invoices so far |
| `quantity_backordered` | Qty still pending fulfillment (`quantity − quantity_invoiced`) |
| `has_backorder` | `true` if **any** item has `quantity_backordered > 0` |

**Identifying backordered products from the `items` list:**
```json
// Filter client-side for items still on backorder:
items.filter(item => item.quantity_backordered > 0)
// Example result:
[
  {
    "inward_id": "B2B-INW26AAAA0001",
    "sku_no": "VEGA-BOLT-M-RED",
    "name": "Vega Bolt Medium Red",
    "quantity": 10,
    "quantity_invoiced": 8,
    "quantity_backordered": 2
  },
  {
    "inward_id": "B2B-INW26AAAA0002",
    "sku_no": "VEGA-EDGE-L-BLK",
    "name": "Vega Edge Large Black",
    "quantity": 5,
    "quantity_invoiced": 0,
    "quantity_backordered": 5
  }
]
```

> **Note:** There is no separate backorder endpoint. The `items` array always carries live backorder tracking per item. Use `has_backorder: true` as the flag and filter `items` where `quantity_backordered > 0` to get the full backorder product list.

---

### 7.5 Track Order (Public)

#### `GET /api/v1/b2b-orders/track/{order_id}`
Publicly track an order's dispatch status and history by Order ID (no auth required).

**Response:**
```json
{
  "order_id": "B2BORD26AAAA0001",
  "status": "Dispatched",
  "total_items": 10,
  "total_price": 200.0,
  "dispatch_details": {
    "courier_name": "Delhivery",
    "tracking_number": "1234567890",
    "estimated_delivery": "2026-06-10",
    "dispatched_at": "2026-06-07T08:00:00",
    "dispatched_by": "USR_ADMIN"
  },
  "status_history": [ ... ],
  "po_url": "/api/v1/b2b-orders/B2BORD26AAAA0001/po",
  "tracking_url": "https://www.delhivery.com/track/package/1234567890",
  "created_at": "...",
  "updated_at": "..."
}
```

**Courier Tracking URLs auto-generated for:** Delhivery, DTDC, Blue Dart, FedEx, DHL, India Post / Speed Post.

---

### 7.6 Admin Order Actions

#### `PATCH /api/v1/b2b-orders/{order_id}/status`
Update order status.

**Request Body:**
```json
{ "status": "Processing", "note": "Picked and packed" }
```
**Valid statuses:** `Pending`, `Confirmed`, `Processing`, `Dispatched`, `Delivered`, `Cancelled`

---

#### `PATCH /api/v1/b2b-orders/{order_id}/cancel`
Cancel an order with a reason.

**Request Body:**
```json
{ "reason": "Out of stock" }
```

---

#### `PATCH /api/v1/b2b-orders/{order_id}/dispatch`
Mark an order as Dispatched and attach courier details.

**Request Body:**
```json
{
  "courier_name": "Delhivery",
  "tracking_number": "1234567890",
  "estimated_delivery": "2026-06-10",
  "note": "Dispatched from Belagavi warehouse"
}
```

---

#### `PATCH /api/v1/b2b-orders/{order_id}/note`
Add or update an admin note on the order.

**Request Body:**
```json
{ "note": "Priority shipment — handle with care" }
```

---

#### `PATCH /api/v1/b2b-orders/{order_id}/payment-status`
Update the payment status of an order.

**Request Body:**
```json
{ "payment_status": "Paid" }
```
**Valid values:** `Paid`, `Unpaid`, `Refunded`

---

#### `POST /api/v1/b2b-orders/admin/bulk-status`
Update status for multiple orders at once.

**Request Body:**
```json
{
  "order_ids": ["B2BORD26AAAA0001", "B2BORD26AAAA0002"],
  "status": "Confirmed",
  "note": "Batch confirmed"
}
```

**Response:**
```json
{
  "updated": ["B2BORD26AAAA0001", "B2BORD26AAAA0002"],
  "failed": [],
  "message": "2 orders updated successfully."
}
```

---

### 7.7 Purchase Order (PO) PDF

#### `GET /api/v1/b2b-orders/{order_id}/po`
Download the Purchase Order PDF for an order. Accessible to both the dealer and admins.

Returns a streaming PDF with:
- Vega logo + company header
- Buyer / Ship-to address
- Order items table with SKU, description, qty, unit price, subtotal
- Order summary: subtotal, discounts, coins redeemed, total

---

### 7.8 Invoice Generation

#### `POST /api/v1/b2b-orders/{order_id}/generate-invoice` _(Admin)_
Generates an invoice against pending (backordered) items. Deducts stock from the B2B catalog.

**Behaviour:**
- Items with insufficient stock remain on **backorder** automatically
- Each call creates a new numbered invoice (e.g. `...-INV-01`, `...-INV-02`)
- Status transitions: `Pending` → `Confirmed` on first invoice
- GST/HST is looked up by the shipping address state; falls back to the default setting

**Optional Request Body (manual qty override):**
```json
{
  "items": [
    { "inward_id": "B2B-INW26AAAA0001", "quantity": 8 }
  ]
}
```
If supplied, only the listed items are invoiced. Unlisted items default to `0`.

**Response (`B2BInvoice`) — items invoiced in this batch:**
```json
{
  "invoice_id": "B2BORD26AAAA0001-INV-01",
  "items": [
    {
      "inward_id": "B2B-INW26AAAA0001",
      "sku_no": "VEGA-BOLT-M-RED",
      "name": "Vega Bolt Medium Red",
      "quantity": 8,
      "dealer_price": 20.0,
      "subtotal": 160.0
    }
  ],
  "subtotal": 160.0,
  "tax_type": "GST",
  "tax_rate": 18.0,
  "tax_amount": 28.8,
  "total_with_tax": 188.8,
  "created_at": "2026-06-07T00:00:00"
}
```

**Remaining backorder items on the order after this invoice:**  
Fetch the updated order via `GET /api/v1/b2b-orders/{order_id}` and filter items where `quantity_backordered > 0`:
```json
[
  {
    "inward_id": "B2B-INW26AAAA0001",
    "sku_no": "VEGA-BOLT-M-RED",
    "name": "Vega Bolt Medium Red",
    "quantity": 10,
    "quantity_invoiced": 8,
    "quantity_backordered": 2,
    "dealer_price": 20.0,
    "currency": "USD",
    "mrp": 25.0
  },
  {
    "inward_id": "B2B-INW26AAAA0002",
    "sku_no": "VEGA-EDGE-L-BLK",
    "name": "Vega Edge Large Black",
    "quantity": 5,
    "quantity_invoiced": 0,
    "quantity_backordered": 5,
    "dealer_price": 18.0,
    "currency": "USD",
    "mrp": 22.0
  }
]
```

> **Tip:** Call `generate-invoice` again once stock is replenished to fulfill remaining backordered items. Each call creates the next invoice (`-INV-02`, `-INV-03`, …).

---

### 7.9 Invoice Preview (Simulate)

#### `POST /api/v1/b2b-orders/{order_id}/preview-invoice` _(Admin)_
Simulates invoice generation without making any DB changes. Use this to confirm what will be invoiced before committing.

**Optional Request Body:** same as `generate-invoice`

**Response (`B2BInvoicePreviewResponse`):**
```json
{
  "items_to_invoice": [
    {
      "inward_id": "B2B-INW26AAAA0001",
      "sku_no": "VEGA-BOLT-M-RED",
      "name": "Vega Bolt Medium Red",
      "quantity": 8,
      "dealer_price": 20.0,
      "subtotal": 160.0
    }
  ],
  "items_to_backorder": [
    {
      "inward_id": "B2B-INW26AAAA0001",
      "sku_no": "VEGA-BOLT-M-RED",
      "name": "Vega Bolt Medium Red",
      "dealer_price": 20.0,
      "currency": "USD",
      "mrp": 25.0,
      "quantity": 10,
      "quantity_invoiced": 8,
      "quantity_backordered": 2,
      "subtotal": 200.0
    },
    {
      "inward_id": "B2B-INW26AAAA0002",
      "sku_no": "VEGA-EDGE-L-BLK",
      "name": "Vega Edge Large Black",
      "dealer_price": 18.0,
      "currency": "USD",
      "mrp": 22.0,
      "quantity": 5,
      "quantity_invoiced": 0,
      "quantity_backordered": 5,
      "subtotal": 90.0
    }
  ],
  "subtotal": 160.0,
  "tax_type": "GST",
  "tax_rate": 18.0,
  "tax_amount": 28.8,
  "total_with_tax": 188.8
}
```

---

### 7.10 Invoice Preview PDF (Watermarked)

#### `POST /api/v1/b2b-orders/{order_id}/preview-invoice/pdf` _(Admin)_
Generates and downloads a **watermarked preview PDF** (`PREVIEW ONLY` diagonal watermark).  
Same optional manual override body as `generate-invoice`.

Returns: `StreamingResponse` (PDF)

---

### 7.11 Invoice PDF Download

#### `GET /api/v1/b2b-orders/{order_id}/invoices/{invoice_id}/pdf`
Download the actual (committed) invoice PDF for a specific invoice ID.  
Accessible to both the dealer (their own orders) and admins.

Returns: `StreamingResponse` (PDF)

---

### 7.12 Dealer Credit Status

#### `GET /api/v1/b2b-orders/dealer/{dealer_id}/credit` _(Admin)_
Returns the dealer's credit limit usage and remaining headroom.

**Response:**
```json
{
  "user_id": "USR26AAAA0001",
  "business_name": "Helmet World",
  "order_credit_limit": 50000.0,
  "overall_credit_limit": 200000.0,
  "outstanding_amount": 45000.0,
  "remaining_credit": 155000.0
}
```

---

## 8. Invoice PDF Layout

**File:** [`app/invoice_generator.py`](file:///Users/hawk/Downloads/vega_traceability_backend/app/invoice_generator.py)

The `generate_invoice_pdf(order_data, invoice_data, dealer_user, is_preview)` function renders an A4 PDF with:

| Section | Content |
|---------|---------|
| **Header** | Vega logo · "TAX INVOICE" title · Invoice number box |
| **Address Block** | Bill To (dealer address + GST) · Supplier (Vega) · Invoice details table |
| **Invoice Details** | Invoice No., Date, Order ID, Order Date, Payment Terms, Currency |
| **Ship To** | Shipping address |
| **Line Items** | `#` · SKU/Item Code · Product Description · Qty Invoiced · Unit Price (INR) · Total (INR) |
| **Footer** | Notes & Special Instructions · Subtotal · GST/HST (rate%) · **Total Payable** |
| **Terms** | Standard B2B credit and dispute terms |
| **Watermark** | `PREVIEW ONLY` diagonal text (only in preview mode) |

**Tax Logic in PDF:**
- `tax_type` + `tax_rate` come from the GST Setting matched to the shipping address state
- If no match found, the `is_default: true` setting is used as fallback

---

## 9. Address-Based GST/HST Tax Settings

### Endpoints

#### `POST /api/v1/b2b-admin/gst-settings/`
```json
{
  "state": "Karnataka",
  "tax_type": "GST",
  "percent": 18.0,
  "is_default": false
}
```

#### `GET /api/v1/b2b-admin/gst-settings/`
Returns list of all state-based GST/HST configurations.

#### `PUT /api/v1/b2b-admin/gst-settings/{setting_id}`
Updates a GST setting.

#### `DELETE /api/v1/b2b-admin/gst-settings/{setting_id}`
Deletes a GST setting.

**Logic:** When generating an invoice, the system:
1. Looks up the shipping address `state`
2. Finds a matching GST setting (case-insensitive)
3. Falls back to the `is_default: true` setting if no match

---

## 10. Packaging Details on Product Submodels

### What Changed
Packaging fields were migrated from the variant level to the **Product Submodel (Graphic Master)** level.

**Fields now on Submodel:**
- `packaging_details`
- `box_and_carton_dimensions`
- `box_weight`
- `box_dimension`
- `carton_weight`
- `carton_dimension`
- `carton_numbers`

**These fields are auto-resolved** into variant responses via `_enrich_variant_fields()`.

---

## 11. Schema Changes Summary

| Schema | Field | Before | After |
|--------|-------|--------|-------|
| `ProductVariantCreate` | `mrp` | `Optional[float]` | `Optional[dict[str, float]]` |
| `ProductVariantUpdate` | `mrp` | `Optional[float]` | `Optional[dict[str, float]]` |
| `JobCardBase` | `currency` | *(missing)* | `Optional[str] = "INR"` |
| `B2BInwardProductCreate` | `currency` | *(missing)* | `Optional[str] = "INR"` |
| `B2BInwardProductUpdate` | `currency` | *(missing)* | `Optional[str] = None` |
| `B2BInwardProduct` | `currency` | *(missing)* | `str = "INR"` |
| `B2BInwardCardResponse` | `currency` | *(missing)* | `str = "INR"` |
| `B2BInwardCardResponse` | `mrp` | `Optional[float]` | `Optional[float]` (resolved) |
| `B2BCartItemResponse` | `currency` | *(missing)* | `str = "INR"` |
| `B2BCartItemResponse` | `mrp` | `Optional[float]` | `Optional[float]` (resolved) |

> **Note:** `B2BInwardCardResponse.mrp` and `B2BCartItemResponse.mrp` remain `Optional[float]` because by the time the response is built, the MRP has already been resolved from the dict to a single float matching the inward's currency.

---

## 12. B2B Submodel-Centric API Refactor

### What Changed
The B2B inward catalog APIs have been refactored to group inwards by **Product Submodel** instead of showing individual variants. This creates a cleaner "parent-level" catalog view, with variants consolidated into the submodel detail page.

### Endpoints Affected

#### `GET /api/v1/b2b-admin/inwards/cards`
**Response Model:** `List[B2BSubmodelCardResponse]`

This endpoint now groups inwarded variants by their `submodel_id` and aggregates flags and pricing.

**Example Response:**
```json
[
  {
    "submodel_id": "PSMD26AA0001",
    "name": "CLASSIC HELMET CLASSIC XOR TRACKER XOR MATTE RED/WHITE",
    "image": "/qrcodes/Variants/PVAR26AA0001/image_1.avif",
    "starting_price": 700.0,
    "currency": "INR",
    "total_variants": 1,
    "is_active": true,
    "is_featured": false,
    "is_new_arrival": true,
    "is_best_seller": false,
    "category_id": "PCAT26AAAA0001",
    "category_name": "HELMET",
    "subcategory_id": "PSUB26AAAA0001",
    "subcategory_name": "HELMET XOR",
    "brand_id": "PBRD26AAAA0003",
    "brand_name": "CLASSIC HELMET",
    "model_id": "PMOD26AA0001",
    "model_name": "CLASSIC XOR TRACKER"
  }
]
```

#### `GET /api/v1/b2b-admin/inwards/{inward_id}` (Treats parameter as `submodel_id`)
**Response Model:** `B2BInwardDetailResponse`

This endpoint now takes a `submodel_id` (passed into the `inward_id` route parameter) and returns the submodel detail along with ALL variants belonging to that submodel.

**Example Response:**
```json
{
  "submodel_detail": {
    "submodel_id": "PSMD26AA0001",
    "name": "XOR MATTE RED/WHITE",
    "image": "/qrcodes/Variants/PVAR26AA0001/image_1.avif",
    "is_active": true,
    "model_id": "PMOD26AA0001",
    "model_name": "CLASSIC XOR TRACKER",
    ...
  },
  "variants": [
    {
      "variant_id": "PVAR26AA0001",
      "sku_no": "CLASSIC-XOR-RED-L",
      "size": 90,
      "size_name": "L",
      "color": "Matte Red/White",
      "finish": "Matte",
      "is_active": true,
      "mrp": 900.0,
      "product_images": [ ... ],
      "b2b_inward": {
        "variant_id": "PVAR26AA0001",
        "dealer_price": 700.0,
        "quantity": null,
        "is_individual": true,
        "is_carton": true,
        "is_featured": false,
        ...
      }
    }
  ]
}
```

> **Note:** This endpoint only returns variants that have been inwarded into the B2B catalog. Non-inwarded variants for the submodel are excluded.
