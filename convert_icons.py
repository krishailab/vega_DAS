from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
import os

icons = ["email.svg", "call.svg", "web.svg", "warning.svg", "book.svg"]
app_dir = "app"

for icon in icons:
    svg_path = os.path.join(app_dir, icon)
    png_path = os.path.join(app_dir, icon.replace(".svg", ".png"))
    if os.path.exists(svg_path):
        try:
            drawing = svg2rlg(svg_path)
            renderPM.drawToFile(drawing, png_path, fmt="PNG")
            print(f"Converted {icon} to PNG")
        except Exception as e:
            print(f"Failed to convert {icon}: {e}")
