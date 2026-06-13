import os
import io
from PIL import Image, ImageDraw, ImageFont

def test_pdf_gen():
    width, height = 800, 1250
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    
    # Load fonts
    try:
        font_path = "venv/lib/python3.9/site-packages/reportlab/fonts/VeraBd.ttf"
        font_bold = ImageFont.truetype(font_path, 24)
        font_regular = ImageFont.truetype("venv/lib/python3.9/site-packages/reportlab/fonts/Vera.ttf", 24)
        font_small = ImageFont.truetype("venv/lib/python3.9/site-packages/reportlab/fonts/Vera.ttf", 16)
    except:
        font_bold = ImageFont.load_default()
        font_regular = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 1. Top Left Logo
    try:
        logo_left = Image.open("app/vegacentral.png")
        logo_left = logo_left.resize((120, 120), Image.Resampling.LANCZOS)
        canvas.paste(logo_left, (50, 50), logo_left if logo_left.mode == 'RGBA' else None)
    except Exception as e:
        print(f"Error loading logo_left: {e}")

    # 2. Top Right Logo
    try:
        vega_logo = Image.open("app/vega.png")
        axor_logo = Image.open("app/axor.png")
        
        # Resize logos
        vega_logo = vega_logo.resize((100, 40), Image.Resampling.LANCZOS)
        axor_logo = axor_logo.resize((100, 40), Image.Resampling.LANCZOS)
        
        canvas.paste(vega_logo, (550, 60), vega_logo if vega_logo.mode == 'RGBA' else None)
        canvas.paste(axor_logo, (660, 60), axor_logo if axor_logo.mode == 'RGBA' else None)
        
        draw.text((655, 110), "central.vegaauto.in", fill="black", font=font_small, anchor="mm")
    except Exception as e:
        print(f"Error loading top right logos: {e}")

    # 3. QR Code (Placeholder)
    qr_display_size = 650
    qr_x = (width - qr_display_size) // 2
    qr_y = 180
    # Create a dummy QR for testing
    qr_dummy = Image.new("RGB", (qr_display_size, qr_display_size), "black")
    canvas.paste(qr_dummy, (qr_x, qr_y))

    # 4. Details Box
    box_y = qr_y + qr_display_size + 40
    box_width = 700
    box_height = 180
    box_x = (width - box_width) // 2
    
    # Draw box border
    draw.rectangle([box_x, box_y, box_x + box_width, box_y + box_height], outline="black", width=2)
    
    # Text inside box
    text_padding = 20
    draw.text((box_x + text_padding, box_y + 20),  "Machine Code: MATT LACQUERING BOOTH 01", fill="black", font=font_bold)
    draw.text((box_x + text_padding, box_y + 65),  "Process: MATT LACQUERING", fill="black", font=font_bold)
    draw.text((box_x + text_padding, box_y + 110), "QR ID: STN26AAAA0006", fill="black", font=font_bold)

    # 5. Footer — logo left, text to the right, both vertically centered
    try:
        footer_logo = Image.open("app/motocross.png")
        footer_h = 50
        orig_w, orig_h = footer_logo.size
        footer_w = int(orig_w * footer_h / orig_h)
        footer_logo = footer_logo.resize((footer_w, footer_h), Image.Resampling.LANCZOS)

        # Vertical center in the footer strip (last 100px)
        footer_strip_top = height - 100
        logo_x = 100
        logo_y = footer_strip_top + (100 - footer_h) // 2

        # Paste logo (handle RGBA vs RGB)
        if footer_logo.mode == 'RGBA':
            canvas.paste(footer_logo, (logo_x, logo_y), footer_logo)
        else:
            canvas.paste(footer_logo, (logo_x, logo_y))

        # Text starts right after logo + small gap
        text_x = logo_x + footer_w + 15
        text_y = footer_strip_top + 50  # vertical center of the strip
        draw.text((text_x, text_y), "Designed & developed by NxtLab | www.nxtlab.in",
                  fill="#444444", font=font_small, anchor="lm")
    except Exception as e:
        print(f"Error loading footer: {e}")

    canvas.save("scratch/test_pdf.png")
    print("Test image saved to scratch/test_pdf.png")

if __name__ == "__main__":
    test_pdf_gen()
