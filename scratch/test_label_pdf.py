import os
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import qrcode
import barcode
from barcode.writer import ImageWriter
import io
from PIL import Image

def generate_pdf():
    # 100mm width, 85mm height
    width_pts = 100 * 2.8346
    height_pts = 85 * 2.8346
    
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=(width_pts, height_pts))
    
    # Draw label border
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.roundRect(4, 4, width_pts - 8, height_pts - 8, 4, stroke=1, fill=0)
    
    # 1. Title / Header
    c.setFont("Helvetica-Bold", 8)
    c.drawString(10, height_pts - 18, "MODEL : BOLT")
    c.drawString(130, height_pts - 18, "MFG : 21/05/2026")
    
    # 2. Details
    c.setFont("Helvetica", 7.5)
    c.drawString(10, height_pts - 30, "STYLE   : VEGA BOLT S NEON RED")
    c.drawString(10, height_pts - 42, "COLOR  : NEON RED")
    c.drawString(10, height_pts - 54, "QTY      : 1 Nos, SIZE : S (Small)")
    c.drawString(10, height_pts - 66, "PRODUCT: VEGA HELMET")
    c.drawString(10, height_pts - 78, "CODE    : VEGA-BOLT-S-RED")
    
    # MRP Bold
    c.setFont("Helvetica", 7.5)
    c.drawString(10, height_pts - 92, "MRP      : ")
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(45, height_pts - 92, "Rs. 2199.00/-")
    c.setFont("Helvetica", 7)
    c.drawString(100, height_pts - 92, "(Incl. of all taxes)")
    
    # Barcodes area (y = 28 to y = 80)
    # Distinct QR Code (PRD)
    qr = qrcode.QRCode(version=1, border=1)
    qr.add_data("PRD26AA00000001")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_io = io.BytesIO()
    qr_img.save(qr_io, format="PNG")
    qr_io.seek(0)
    
    # Draw QR Code image
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(qr_io), 10, 24, width=50, height=50)
    
    # GS1 Barcode (EAN-13)
    try:
        EAN = barcode.get_barcode_class('ean13')
        ean = EAN('8901234567890'[:12], writer=ImageWriter())
        ean.default_writer_options['write_text'] = True
        ean.default_writer_options['font_size'] = 14
        ean.default_writer_options['text_distance'] = 2.0
        barcode_io = io.BytesIO()
        ean.write(barcode_io)
        barcode_io.seek(0)
        c.drawImage(ImageReader(barcode_io), 80, 24, width=190, height=43)
    except Exception as e:
        print("Barcode error:", e)
        
    # Footer text
    c.setFont("Helvetica", 4.5)
    c.drawString(10, 18, "MFG BY: VEGA AUTO ACCESSORIES PVT LTD, PLOT NO. 12/B, SY. NO. 342, UDYAMBAG, BGM KA INDIA-08")
    c.drawString(10, 13, "CUST CARE: VEGA AUTO ACCESSORIES PVT LTD, PLOT NO. 12/B, SY. NO. 342, UDYAMBAG, BGM KA INDIA-08")
    c.drawString(10, 8, "WEB: WWW.VEGAAUTO.COM   EMAIL: CUSTOMERCARE@VEGAAUTO.COM   TEL: 07901014646")

    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()

pdf_data = generate_pdf()
with open("scratch/test_label.pdf", "wb") as f:
    f.write(pdf_data)
print("✓ Label PDF generated successfully in scratch/test_label.pdf")
