import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode
import barcode
from barcode.writer import ImageWriter
import io

def generate_pillow_label(qr_id, sku, barcode_num, mfg_date, model_name, submodel_name, color, size, size_name, mrp, finish, certification):
    # DPI = 300
    # 100mm = 3.937 inches * 300 = 1181 px
    # 85mm = 3.346 inches * 300 = 1004 px
    width = 1181
    height = 1004
    
    # Create white canvas
    img = Image.new("RGBA", (width, height), "white")
    draw = ImageDraw.Draw(img)
    
    # Try to load high-quality fonts or fallback to default
    try:
        font_bold = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36, index=1)
        font_regular = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32, index=0)
        font_mrp = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38, index=1)
        font_footer = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 19, index=0)
    except Exception:
        try:
            font_bold = ImageFont.truetype("Arial Bold", 36)
            font_regular = ImageFont.truetype("Arial", 32)
            font_mrp = ImageFont.truetype("Arial Bold", 38)
            font_footer = ImageFont.truetype("Arial", 19)
        except Exception:
            font_bold = ImageFont.load_default()
            font_regular = ImageFont.load_default()
            font_mrp = ImageFont.load_default()
            font_footer = ImageFont.load_default()
            
    # Draw rounded border
    draw.rounded_rectangle([15, 15, width - 15, height - 15], radius=15, outline="#333333", width=4)
    
    # Left column details x-coordinate
    x_left = 50
    y_start = 50
    line_height = 55
    
    # Header: Model & MFG Date
    draw.text((x_left, y_start), "MODEL :", fill="black", font=font_bold)
    draw.text((x_left + 160, y_start), str(model_name).upper(), fill="black", font=font_bold)
    
    draw.text((width - 480, y_start), f"MFG : {mfg_date}", fill="black", font=font_bold)
    
    # Details
    y = y_start + line_height + 10
    draw.text((x_left, y), "STYLE    :", fill="black", font=font_regular)
    draw.text((x_left + 180, y), str(submodel_name).upper(), fill="black", font=font_regular)
    
    y += line_height
    draw.text((x_left, y), "COLOR   :", fill="black", font=font_regular)
    draw.text((x_left + 180, y), str(color).upper(), fill="black", font=font_regular)
    
    y += line_height
    draw.text((x_left, y), "QTY       :", fill="black", font=font_regular)
    if size is not None:
        size_str = f"{size} ({size_name})" if size_name else str(size)
    else:
        size_str = size_name if size_name else "N/A"
    draw.text((x_left + 180, y), f"1 Nos, SIZE : {size_str}", fill="black", font=font_regular)
    
    y += line_height
    draw.text((x_left, y), "PRODUCT :", fill="black", font=font_regular)
    draw.text((x_left + 180, y), "VEGA HELMET" if "VEGA" in str(sku).upper() else "AXOR HELMET", fill="black", font=font_regular)
    
    y += line_height
    draw.text((x_left, y), "CODE     :", fill="black", font=font_regular)
    draw.text((x_left + 180, y), str(sku).upper(), fill="black", font=font_regular)
    
    y += line_height
    draw.text((x_left, y), "MRP : Rs.", fill="black", font=font_regular)
    draw.text((x_left + 180, y), f"{mrp:,.2f}/-", fill="black", font=font_mrp)
    draw.text((x_left + 420, y), "(Incl. of all taxes)", fill="black", font=font_regular)
    
    # Generate and draw QR Code (PRD ID) on right side
    qr = qrcode.QRCode(version=1, border=1)
    qr.add_data(qr_id)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    qr_img = qr_img.resize((260, 260))
    img.paste(qr_img, (width - 320, 200))
    
    # Text under QR Code
    draw.text((width - 310, 465), f"PRD QR: {qr_id}", fill="black", font=font_regular)
    
    try:
        gs1_digits = "".join(ch for ch in barcode_num if ch.isdigit())
        if len(gs1_digits) >= 12:
            gs1_for_barcode = gs1_digits[:12]
        else:
            gs1_for_barcode = gs1_digits.zfill(12)

        EAN = barcode.get_barcode_class('ean13')
        ean = EAN(gs1_for_barcode, writer=ImageWriter())
        ean.default_writer_options['write_text'] = True
        ean.default_writer_options['font_size'] = 14
        ean.default_writer_options['text_distance'] = 2.0
        
        barcode_io = io.BytesIO()
        ean.write(barcode_io)
        barcode_io.seek(0)
        
        bar_img = Image.open(barcode_io).convert("RGBA")
        # Resize to fit nicely
        bar_img = bar_img.resize((700, 160))
        img.paste(bar_img, (50, 620))
    except Exception as e:
        print("Barcode render error:", e)
        
    # Footer text
    y_footer = 860
    draw.text((50, y_footer), "MFG BY: VEGA AUTO ACCESSORIES PVT LTD, PLOT NO. 12/B, SY. NO. 342, UDYAMBAG, BGM KA INDIA-08", fill="#333333", font=font_footer)
    draw.text((50, y_footer + 30), "CUST CARE: VEGA AUTO ACCESSORIES PVT LTD, PLOT NO. 12/B, SY. NO. 342, UDYAMBAG, BGM KA INDIA-08", fill="#333333", font=font_footer)
    draw.text((50, y_footer + 60), "WEB: WWW.VEGAAUTO.COM   EMAIL: CUSTOMERCARE@VEGAAUTO.COM   TEL: 07901014646", fill="#333333", font=font_footer)
    
    # Save preview image
    preview_path = "/Users/hawk/.gemini/antigravity-ide/brain/34f31266-cfae-4926-a7c9-ef2939651f06/label_preview.png"
    img.save(preview_path, "PNG")
    print(f"✓ Beautiful preview image saved to {preview_path}")

generate_pillow_label(
    qr_id="PRD26AA00000001",
    sku="AXR-APX-PRISM-WMB-L",
    barcode_num="8901234567890",
    mfg_date="21/05/2026",
    model_name="APEX",
    submodel_name="APEX PRISM",
    color="WHITE BLUE",
    size=None,
    size_name="Large (600 mm)",
    mrp=4994.0,
    finish="Gloss",
    certification=["DOT", "ISI"]
)
