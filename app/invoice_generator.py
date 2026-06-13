import io
import os
from datetime import datetime, timedelta
from .utils import get_currency_symbol
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import mm

def generate_invoice_pdf(order_data: dict, invoice_data: dict, dealer_user: dict, is_preview: bool = False) -> io.BytesIO:
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
    
    supplier_style = ParagraphStyle(
        name='SupplierStyle',
        parent=normal_style,
        fontSize=8.5,
        leading=11
    )
    
    centered_title_style = ParagraphStyle(
        name='CenteredTitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#2c3e50'),
        alignment=1 # Center
    )
    
    title_style = ParagraphStyle(
        name='TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=28,
        textColor=colors.HexColor('#2c3e50'),
        alignment=2 # Right
    )
    
    large_amt_style = ParagraphStyle(
        name='LargeAmtStyle',
        parent=normal_style,
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
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
    
    right_normal = ParagraphStyle(
        name='RightNormal',
        parent=normal_style,
        alignment=2 # Right
    )
    
    bold_style = ParagraphStyle(
        name='BoldStyle',
        parent=normal_style,
        fontName='Helvetica-Bold'
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
    
    is_paid = (order_data.get("payment_status") == "Paid")
    title_text = "Invoice" if is_paid else "Proforma Invoice"
    title_p = Paragraph(title_text.upper(), centered_title_style)
    elements.append(title_p)
    elements.append(Spacer(1, 5*mm))
    
    # 2. HEADER: Issuer (Daytona Classic Ltd on the Left) vs Balance Due (Right)
    logo_path = os.path.join(os.path.dirname(__file__), "classic.png")
    logo_element = None
    if os.path.exists(logo_path):
        logo_element = Image(logo_path, width=45*mm, height=15*mm)
        
    supplier_html = f"""
    Daytona Classic Ltd<br/>
    Edmonton Alberta T5N 0Z1<br/>
    Canada<br/>
    +1-800-668-3871<br/>
    Sales@classicbeanie.com
    """
    
    supplier_flowable = []
    if logo_element:
        supplier_flowable.append(logo_element)
        supplier_flowable.append(Spacer(1, 3*mm))
    supplier_flowable.append(Paragraph(supplier_html, supplier_style))
    inv_currency = "INR"
    for item in invoice_data.get("items", []):
        if item.get("currency"):
            inv_currency = item.get("currency")
            break
    else:
        for item in order_data.get("items", []):
            if item.get("currency"):
                inv_currency = item.get("currency")
                break
    curr_sym = get_currency_symbol(inv_currency)
    
    total_val = invoice_data.get("total_with_tax", invoice_data.get("subtotal", 0.0))
    balance_due_str = f"{curr_sym}{total_val:,.2f}"
    
    right_flowables = [
        Paragraph(f'<font size="10"># {invoice_data.get("invoice_id", "")}</font>', right_normal),
        Spacer(1, 4*mm),
        Paragraph('<font size="8" color="#7f8c8d"><b>Balance Due</b></font>', right_normal),
        Spacer(1, 1*mm),
        Paragraph(balance_due_str, right_bold_large)
    ]
    #dfghjk
    header_table = Table([[supplier_flowable, right_flowables]], colWidths=[110*mm, 70*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8*mm))
    billing_address = order_data.get('billing_address') or order_data.get('company_address') or {}
    b_addr = billing_address.get('address_line', '')
    b_city = billing_address.get('city', '')
    b_state = billing_address.get('state', '')
    b_pin = billing_address.get('pincode', '')
    b_phone = billing_address.get('alternate_mobile') or billing_address.get('business_mobile') or dealer_user.get('mobile') or ''
    b_email = billing_address.get('business_email') or dealer_user.get('email') or ''
    
    bill_to_name = (
        billing_address.get('business_name') or
        billing_address.get('name') or
        dealer_user.get('business_name') or
        f"{dealer_user.get('first_name', '')} {dealer_user.get('last_name', '')}".strip()
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
    s_phone = shipping_address.get('alternate_mobile') or shipping_address.get('business_mobile') or dealer_user.get('mobile') or ''
    
    ship_to_name = (
        shipping_address.get('business_name') or
        shipping_address.get('name') or
        dealer_user.get('business_name') or
        f"{dealer_user.get('first_name', '')} {dealer_user.get('last_name', '')}".strip()
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
    
    inv_date = invoice_data.get("created_at")
    if isinstance(inv_date, datetime):
        inv_date_str = inv_date.strftime("%Y/%m/%d")
        due_date = inv_date + timedelta(days=30)
        due_date_str = due_date.strftime("%Y/%m/%d")
    else:
        inv_date_str = str(inv_date) if inv_date else ""
        due_date_str = ""
        
    payment_terms = str(order_data.get("payment_type", "Net 30")).replace("_", " ").title()
    po_no = order_data.get("order_id", "")
    
    meta_html = f"""
    <b>Invoice Date :</b> {inv_date_str}<br/>
    <b>Terms :</b> {payment_terms}<br/>
    <b>Due Date :</b> {due_date_str}<br/>
    <b>P.O.# :</b> {po_no}
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
    # ITEMS TABLE
    # -------------------------------------------------------------------------
    items_headers = [
        Paragraph("<b>#</b>", table_header_style),
        Paragraph("<b>Item & Description</b>", table_header_style),
        Paragraph("<b>Qty</b>", table_header_style_right),
        Paragraph(f"<b>Rate ({curr_sym})</b>", table_header_style_right),
        Paragraph(f"<b>Amount ({curr_sym})</b>", table_header_style_right)
    ]
    items_rows = [items_headers]
    
    for idx, item in enumerate(invoice_data.get("items", [])):
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3c3b37')),
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
    subtotal_val = invoice_data.get("subtotal", 0.0)
    tax_type = invoice_data.get("tax_type", "GST")
    tax_rate = invoice_data.get("tax_rate", 0.0)
    tax_amount = invoice_data.get("tax_amount", 0.0)
    
    totals_rows = [
        ["Sub Total", f"{subtotal_val:,.2f}"]
    ]
    if tax_amount > 0:
        totals_rows.append([f"{tax_type} ({tax_rate}%)", f"{tax_amount:,.2f}"])
    totals_rows.append(["Balance Due", f"{curr_sym}{total_val:,.2f}"])
    
    totals_table = Table(totals_rows, colWidths=[130*mm, 50*mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (1,0), (1,-1), 0),
    ]))
    elements.append(totals_table)
    
    # Watermark for preview
    if is_preview:
        def draw_watermark(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica-Bold', 60)
            canvas.setFillColor(colors.HexColor('#d3d3d3'), alpha=0.35)
            canvas.translate(297, 420)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "PREVIEW ONLY")
            canvas.restoreState()
        
        doc.build(elements, onFirstPage=draw_watermark, onLaterPages=draw_watermark)
    else:
        doc.build(elements)
        
    buffer.seek(0)
    return buffer

