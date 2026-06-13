import io
import os
from datetime import datetime
from .utils import get_currency_symbol
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import mm

def generate_po_pdf(order_data: dict, user_data: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    
    # Setup document with 15mm margins
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=15*mm, leftMargin=15*mm, 
        topMargin=15*mm, bottomMargin=15*mm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    normal_style = styles['Normal']
    normal_style.fontSize = 8.5
    normal_style.leading = 11.5
    normal_style.textColor = colors.HexColor('#2c3e50')
    
    centered_title_style = ParagraphStyle(
        name='CenteredTitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        alignment=1 # Center
    )
    
    supplier_style = ParagraphStyle(
        name='SupplierStyle',
        parent=normal_style,
        fontSize=8.5,
        leading=11
    )
    
    right_normal = ParagraphStyle(
        name='RightNormal',
        parent=normal_style,
        alignment=2 # Right
    )
    
    right_bold_large = ParagraphStyle(
        name='RightBoldLarge',
        parent=normal_style,
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=2 # Right
    )
    
    table_header_style = ParagraphStyle(
        name='TableHeaderStyle',
        parent=normal_style,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )

    table_header_style_right = ParagraphStyle(
        name='TableHeaderStyleRight',
        parent=table_header_style,
        alignment=2
    )
    
    # 1. Title (Centered at the top)
    title_p = Paragraph("PURCHASE ORDER", centered_title_style)
    elements.append(title_p)
    elements.append(Spacer(1, 5*mm))
    
    # 2. HEADER: Issuer (Daytona Classic Ltd on the Left) vs Total Amount (Right)
    logo_path = os.path.join(os.path.dirname(__file__), "classic.png")
    logo_element = None
    if os.path.exists(logo_path):
        logo_element = Image(logo_path, width=45*mm, height=15*mm)
        
    issuer_html = f"""
    Daytona Classic Ltd<br/>
    Edmonton Alberta T5N 0Z1<br/>
    Canada<br/>
    +1-800-668-3871<br/>
    Sales@classicbeanie.com
    """
    
    issuer_flowable = []
    if logo_element:
        issuer_flowable.append(logo_element)
        issuer_flowable.append(Spacer(1, 3*mm))
    issuer_flowable.append(Paragraph(issuer_html, supplier_style))
    
    # Totals/Currency
    po_currency = "INR"
    for item in order_data.get("items", []):
        if item.get("currency"):
            po_currency = item.get("currency")
            break
    curr_sym = get_currency_symbol(po_currency)
    
    total_val = order_data.get("total_price", 0.0)
    total_str = f"{curr_sym}{total_val:,.2f}"
    
    right_flowables = [
        Paragraph(f'<font size="10"># {order_data.get("order_id", "")}</font>', right_normal),
        Spacer(1, 4*mm),
        Paragraph('<font size="8" color="#7f8c8d"><b>Total Amount</b></font>', right_normal),
        Spacer(1, 1*mm),
        Paragraph(total_str, right_bold_large)
    ]
    
    header_table = Table([[issuer_flowable, right_flowables]], colWidths=[110*mm, 70*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8*mm))
    
    # -------------------------------------------------------------------------
    # BILL TO / SHIP TO / DETAILS SECTION
    # -------------------------------------------------------------------------
    billing_address = order_data.get('billing_address') or order_data.get('company_address') or {}
    b_addr = billing_address.get('address_line', '')
    b_city = billing_address.get('city', '')
    b_state = billing_address.get('state', '')
    b_pin = billing_address.get('pincode', '')
    b_phone = billing_address.get('alternate_mobile') or billing_address.get('business_mobile') or user_data.get('mobile') or ''
    
    bill_to_name = (
        billing_address.get('business_name') or
        billing_address.get('name') or
        user_data.get('business_name') or
        f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
    )
    
    bill_to_html = f"""
    <font size="9" color="#7f8c8d"><b>Bill To</b></font><br/>
    """
    if bill_to_name:
        bill_to_html += f"<b>{bill_to_name}</b><br/>"
    b_contact_name = billing_address.get('name')
    if b_contact_name and str(b_contact_name).strip() and str(b_contact_name).strip() != str(bill_to_name).strip():
        bill_to_html += f"{b_contact_name}<br/>"
    bill_to_html += f"""
    {b_addr}<br/>
    {b_city}, {b_state} {b_pin}<br/>
    """
    b_country = billing_address.get('country', '').strip()
    if b_country:
        bill_to_html += f"{b_country}<br/>"
    if b_phone:
        bill_to_html += f"Phone: {b_phone}"
    
    shipping_address = order_data.get('shipping_address') or order_data.get('company_address') or {}
    s_addr = shipping_address.get('address_line', '')
    s_city = shipping_address.get('city', '')
    s_state = shipping_address.get('state', '')
    s_pin = shipping_address.get('pincode', '')
    s_phone = shipping_address.get('alternate_mobile') or shipping_address.get('business_mobile') or user_data.get('mobile') or ''
    
    ship_to_name = (
        shipping_address.get('business_name') or
        shipping_address.get('name') or
        user_data.get('business_name') or
        f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
    )
    
    ship_to_html = f"""
    <font size="9" color="#7f8c8d"><b>Ship To</b></font><br/>
    """
    if ship_to_name:
        ship_to_html += f"<b>{ship_to_name}</b><br/>"
    s_contact_name = shipping_address.get('name')
    if s_contact_name and str(s_contact_name).strip() and str(s_contact_name).strip() != str(ship_to_name).strip():
        ship_to_html += f"{s_contact_name}<br/>"
    ship_to_html += f"""
    {s_addr}<br/>
    {s_city}, {s_state} {s_pin}<br/>
    """
    s_country = shipping_address.get('country', '').strip()
    if s_country:
        ship_to_html += f"{s_country}<br/>"
    if s_phone:
        ship_to_html += f"Phone: {s_phone}"
    
    order_date = order_data.get("created_at")
    if isinstance(order_date, datetime):
        order_date_str = order_date.strftime("%Y/%m/%d")
    else:
        order_date_str = str(order_date) if order_date else ""
        
    payment_terms = str(order_data.get("payment_type", "now")).upper()
    
    meta_html = f"""
    <b>PO Date :</b> {order_date_str}<br/>
    <b>Payment Terms :</b> {payment_terms}<br/>
    <b>Incoterms :</b> FOB<br/>
    <b>Currency :</b> {po_currency}
    """
    
    addr_details_table = Table([
        [Paragraph(bill_to_html, normal_style), Paragraph(ship_to_html, normal_style), Paragraph(meta_html, right_normal)]
    ], colWidths=[62*mm, 62*mm, 56*mm])
    addr_details_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(addr_details_table)
    elements.append(Spacer(1, 8*mm))
    
    # -------------------------------------------------------------------------
    # ITEMS TABLE (Black and White Color Theme)
    # -------------------------------------------------------------------------
    items_headers = [
        Paragraph("<b>#</b>", table_header_style),
        Paragraph("<b>Item & Description</b>", table_header_style),
        Paragraph("<b>Qty</b>", table_header_style_right),
        Paragraph(f"<b>Rate ({curr_sym})</b>", table_header_style_right),
        Paragraph(f"<b>Amount ({curr_sym})</b>", table_header_style_right)
    ]
    items_rows = [items_headers]
    
    for idx, item in enumerate(order_data.get("items", [])):
        qty_val = float(item.get("quantity", 0))
        rate_val = float(item.get("dealer_price", 0.0))
        amt_val = float(item.get("subtotal", 0.0))
        
        desc_line = f"{item.get('sku_no', '')} - {item.get('name', '')}"
        
        items_rows.append([
            str(idx + 1),
            Paragraph(desc_line, normal_style),
            f"{qty_val:.2f}",
            f"{rate_val:,.2f}",
            f"{amt_val:,.2f}"
        ])
        
    items_table = Table(items_rows, colWidths=[10*mm, 100*mm, 20*mm, 25*mm, 25*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3c3b37')), # Black/Charcoal header for BW look
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
        ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.HexColor('#e0e0e0')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (1,0), (1,-1), 2),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4*mm))
    
    # -------------------------------------------------------------------------
    # TOTALS SECTION
    # -------------------------------------------------------------------------
    subtotal = order_data.get("subtotal", order_data.get("total_price", 0.0))
    discount = order_data.get("discount_applied", 0.0)
    
    totals_rows = [
        ["Sub Total", f"{subtotal:,.2f}"]
    ]
    if discount > 0:
        totals_rows.append(["Discount Applied", f"-{discount:,.2f}"])
    totals_rows.append(["Total PO Value", f"{curr_sym}{total_val:,.2f}"])
    
    totals_table = Table(totals_rows, colWidths=[130*mm, 50*mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (1,0), (1,-1), 0),
    ]))
    elements.append(totals_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
