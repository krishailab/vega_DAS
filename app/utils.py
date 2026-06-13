from datetime import datetime, timezone, timedelta
import qrcode
from qrcode.image.pil import PilImage
import io
import base64
import os

IST = timezone(timedelta(hours=5, minutes=30))

def get_current_time():
    return datetime.now(IST).replace(tzinfo=None)

def generate_custom_id(prefix: str, collection, id_field: str, digits: int = 4) -> str:
    current_year = get_current_time().year
    yy = str(current_year)[-2:]
    
    count_this_year = collection.count_documents({id_field: {"$regex": f"^{prefix}{yy}"}})
    
    max_count = 10**digits - 1
    
    attempts = 0
    while True:
        current_count = count_this_year + attempts
        xx_index = current_count // max_count
        count = (current_count % max_count) + 1

        c = chr(65 + xx_index % 26)
        custom_id = f"{prefix}{yy}{c}{count:0{digits}d}"
            
        if not collection.find_one({id_field: custom_id}):
            return custom_id
        attempts += 1

def generate_custom_ids(prefix: str, collection, id_field: str, amount: int, digits: int = 4) -> list[str]:
    current_year = get_current_time().year
    yy = str(current_year)[-2:]
    
    count_this_year = collection.count_documents({id_field: {"$regex": f"^{prefix}{yy}"}})
    
    max_count = 10**digits - 1
    ids = []
    
    attempts = 0
    while len(ids) < amount:
        current_count = count_this_year + attempts
        xx_index = current_count // max_count
        count = (current_count % max_count) + 1
        
        c = chr(65 + xx_index % 26)
        custom_id = f"{prefix}{yy}{c}{count:0{digits}d}"
            
        if not collection.find_one({id_field: custom_id}) and custom_id not in ids:
            ids.append(custom_id)
        attempts += 1
        
    return ids

def generate_qr_base64(data: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def generate_qr_file(data: str, master_admin_id: str, category: str, entity_id: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
    img = img.convert("RGB")
    
    dir_path = os.path.join("qrcodes", master_admin_id, category)
    os.makedirs(dir_path, exist_ok=True)
    
    file_path = os.path.join(dir_path, f"{entity_id}.jpeg")
    img.save(file_path, format="JPEG")
    
    return file_path

def generate_dynamic_product_qr_ids(part_name: str, plant_id: str, amount: int) -> list[str]:
    """
    Generate *amount* globally-unique QR IDs for the given part and plant.

    Format:  {first_letter}{plant_code}{YY}{AAA}{NNNN}
    Example: SA26AAA3982

    Uniqueness is guaranteed by:
      1. Finding the highest existing numeric suffix for this prefix (not count)
      2. Skipping any candidate ID already in qr_master (collision-proof loop)
    """
    import re as _re
    from .database import qr_master_collection, plants_collection

    # 1. First letter of part name
    first_letter = part_name[0].upper() if part_name else "P"

    # 2. Plant code  (0→A, 1→B, … 25→Z, 26→ZA, …)
    plants = list(plants_collection.find({}, sort=[("plant_id", 1)]))
    plant_ids = [p["plant_id"] for p in plants]
    try:
        plant_index = plant_ids.index(plant_id) if plant_id in plant_ids else 0
    except Exception:
        plant_index = 0
    num_zs    = plant_index // 26
    remainder = plant_index % 26
    plant_code = ("Z" * num_zs) + chr(65 + remainder)

    current_year = get_current_time().year
    yy = str(current_year)[-2:]

    prefix = f"{first_letter}{plant_code}{yy}"   # e.g. "SA26"

    # 3. Find the highest numeric suffix already in use for this prefix
    #    Using max instead of count makes this immune to gaps and duplicates.
    _suffix_re = _re.compile(r'^' + _re.escape(prefix) + r'[A-Z]{3}(\d{4})$')
    max_num = 0
    for doc in qr_master_collection.find(
        {"qr_id": {"$regex": f"^{prefix}"}},
        {"qr_id": 1, "_id": 0}
    ):
        m = _suffix_re.match(doc["qr_id"])
        if m:
            n = int(m.group(1))
            if n > max_num:
                max_num = n

    # Also find the max letter block (AAA, AAB, …)
    _letter_re = _re.compile(r'^' + _re.escape(prefix) + r'([A-Z]{3})(\d{4})$')
    max_letter_index = 0
    for doc in qr_master_collection.find(
        {"qr_id": {"$regex": f"^{prefix}"}},
        {"qr_id": 1, "_id": 0}
    ):
        m = _letter_re.match(doc["qr_id"])
        if m:
            letters = m.group(1)           # e.g. "AAA"
            c1 = ord(letters[0]) - 65
            c2 = ord(letters[1]) - 65
            c3 = ord(letters[2]) - 65
            li = c1 * 26 * 26 + c2 * 26 + c3
            num = int(m.group(2))
            # Flatten to a single global index
            global_idx = li * 9999 + (num - 1)
            if global_idx > max_letter_index:
                max_letter_index = global_idx

    # Start from the next index after the current maximum
    next_global = max_letter_index + 1

    # Pre-load existing QR IDs for fast collision check
    existing = set(
        d["qr_id"]
        for d in qr_master_collection.find(
            {"qr_id": {"$regex": f"^{prefix}"}},
            {"qr_id": 1, "_id": 0}
        )
    )

    ids: list[str] = []
    candidate_idx = next_global

    while len(ids) < amount:
        # Decompose global index back into letters + 4-digit number
        letter_index = candidate_idx // 9999
        num_part     = (candidate_idx % 9999) + 1

        c3 = chr(65 + (letter_index % 26))
        c2 = chr(65 + ((letter_index // 26) % 26))
        c1 = chr(65 + ((letter_index // (26 ** 2)) % 26))
        letters = f"{c1}{c2}{c3}"

        candidate = f"{prefix}{letters}{num_part:04d}"

        if candidate not in existing:
            ids.append(candidate)
            existing.add(candidate)   # prevent intra-batch collision

        candidate_idx += 1

    return ids


def get_currency_symbol(currency_code: str) -> str:
    if not currency_code:
        return "Rs."
    # Standardize to uppercase
    code = currency_code.strip().upper()
    
    # Common currency symbols mapping
    symbols = {
        "INR": "Rs.",
        "USD": "$",
        "CAD": "C$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "CNY": "¥",
        "AUD": "A$",
        "NZD": "NZ$",
        "CHF": "CHF",
        "SGD": "S$",
        "HKD": "HK$",
        "SEK": "kr",
        "NOK": "kr",
        "DKK": "kr",
        "RUB": "₽",
        "TRY": "₺",
        "BRL": "R$",
        "ZAR": "R",
        "MXN": "$",
        "PLN": "zł",
        "PHP": "₱",
        "IDR": "Rp",
        "THB": "฿",
        "MYR": "RM",
        "KRW": "₩",
        "AED": "AED",
        "SAR": "SAR",
    }
    return symbols.get(code, code)

