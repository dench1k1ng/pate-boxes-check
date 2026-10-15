# -*- coding: utf-8 -*-
"""Parser for simple daily discount lists from Tortikipirogi and other venues.

Supported formats (both may appear in one message)::

    Трайфл медовый-760
    Круассан с семгой 1800, со скидкой 1440
    27.09 KULINAR&CA. Цена за 1 шт
    Клаб сэндвич с курицей 665 вместо 950 (в наличии 2 шт)
    Coffi | Бокейхана 10
    Бейгл с курицей 1/1890
    🧡 Бокс №1 — Сытный 🥐
    🥐 Круассан с семгой — 925 ₸
    💰 Итого: 925 ₸

Unlike the Pâté parser, this parser deliberately does not use a product
catalogue or rename product names. Each product line or named box becomes a
CRM-ready card. Box components are retained in the description; the total is
the price after a 50% discount. The venue comes from the UI or message header,
falling back to Tortikipirogi.
"""
import datetime
import html
import re
from pathlib import Path


STORE_NAME = "Tortikipirogi"
CATEGORY_NAME = "Кондитерские изделия"
DEFAULT_DISCOUNT_PCT = 20
COFFI_DEFAULT_DISCOUNT_PCT = 60
COFFI_TODAY_DISCOUNT_PCT = 50
DEFAULT_EXPIRY_DAYS = 1
STATUS = "AVAILABLE"
# As in the existing priced-box format, the supplied total is the sale price.
BOX_ORIGINAL_PRICE_MULTIPLIER = 2
TORTIKI_IMAGE_ROOT = "images/tortiki"
BOX_POINT_HEADERS = {"сыганак 3": "Royalty Coffee | Сыганак 3"}
PRICED_BOX_HEADER_RE = re.compile(r"^бокс\s*№?\s*(?P<number>\d+)\s*[-–—]\s*(?P<price>\d+)$", re.IGNORECASE)
BOX_HEADER_RE = re.compile(r"^бокс\s*№?\s*(?P<number>\d+)\s*[-–—]\s*(?P<title>.+)$", re.IGNORECASE)
BOX_COMPONENT_RE = re.compile(r"^(?P<name>.+?)\s*[-–—]\s*(?P<price>\d+)$")
BOX_QUANTITY_RE = re.compile(
    r"^(?P<name>.+?)\s*[-–—]\s*(?P<qty>\d+)\s*(?P<unit>шт|штуки|штук|порция|порции|пор|уп)?$",
    re.IGNORECASE,
)
BOX_TOTAL_RE = re.compile(r"^итого\s*:\s*(?P<price>\d+)$", re.IGNORECASE)
COFFI_HEADER_RE = re.compile(r"^coffi\s*\|\s*.+$", re.IGNORECASE)


def is_coffi_store(store_name):
    return re.match(r"^coffi(?:\s*\||$)", str(store_name or "").strip(), re.IGNORECASE) is not None


def clean_box_line(line):
    text = clean_line(html.unescape(line).replace("\u202f", " "))
    # Remove decorative emoji at the edges, retaining punctuation inside names.
    return re.sub(r"^[^\w]+|[^\w]+$", "", text).strip()


def build_box_card(box, expiry_days):
    components = box["components"]
    reasons = list(box["reasons"])
    total = box["price"] if box["price"] is not None else box["total"]
    if box["price"] is None:
        if total is None:
            total = sum(price for _, price in components)
            reasons.append("не указана строка Итого; цена рассчитана по составу")
        elif total != sum(price for _, price in components):
            reasons.append("сумма цен состава не совпадает с Итого")
    if not components:
        reasons.append("не указан состав бокса")
    if any(value <= 0 for _, value in components):
        reasons.append("количество компонента должно быть больше нуля" if box["price"] is not None else "цена компонента должна быть больше нуля")
    parsed = make_parsed(
        box["name"], total, round(total * BOX_ORIGINAL_PRICE_MULTIPLIER),
        1, None, assumed_discount=True,
    )
    parsed["reviewReasons"].extend(reasons)
    card = build_card(parsed, expiry_days, box["store"])
    card["description"] = "Состав:\n" + "\n".join(box["description"])
    return card


def _image_key(value):
    """Normalize a product/photo name for tolerant filename matching."""
    value = str(value or "").lower().replace("ё", "е")
    value = re.sub(r"^\d+[_ .-]*", "", value)
    value = value.replace("_", " ").replace("-", " ")
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def _load_tortiki_images():
    root = Path(__file__).resolve().parent / TORTIKI_IMAGE_ROOT
    if not root.exists():
        return {}
    images = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        relative = path.relative_to(Path(__file__).resolve().parent).as_posix()
        images[_image_key(path.stem)] = relative
    return images


TORTIKI_IMAGES = _load_tortiki_images()
TORTIKI_IMAGE_ALIASES = {
    "баннофи пай": "банофи пай",
    "баннофи пай мини": "банофи пай mini",
    "пицци мини": "пицца mini",
    "самса курица мясо": "самса с мясом или курицей",
    "самса с мясом": "самса с мясом или курицей",
    "самса с курицей": "самса с мясом или курицей",
}


def image_for_product(name):
    key = _image_key(name)
    key = _image_key(TORTIKI_IMAGE_ALIASES.get(key, key))
    if key in TORTIKI_IMAGES:
        return TORTIKI_IMAGES[key]
    return None

SEPARATOR_RE = re.compile(r"^[-=_*]{3,}\s*$")
QUANTITY_RE = re.compile(
    r"(?:(?:в\s+наличии)\s*)?\b(?P<qty>\d+)\s*(?P<unit>шт(?:\.?|ук)?|штук|порц(?:ия|ии|ию|ий)?|пор|уп(?:ак(?:овк[аи])?)?)\b",
    re.IGNORECASE,
)
NUMBER_WITH_SEPARATOR_RE = re.compile(r"(?<!\w)\d{1,3}(?:[ .]\d{3})+(?!\w)")
CURRENCY_RE = re.compile(r"(?<=\d)\s*(?:тенге|тг|₸|т)(?=\s|$|[,.;])", re.IGNORECASE)
VENUE_HEADER_RE = re.compile(
    r"^\s*(?:\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\s+)?"
    r"(?P<store>[^.\n]+?)\s*\.\s*цена\s+за\s+1\s*"
    r"(?:шт\.?|штук|единиц[ау])(?:\s|$)",
    re.IGNORECASE,
)


def normalize_number_separators(text):
    return NUMBER_WITH_SEPARATOR_RE.sub(lambda m: m.group(0).replace(".", "").replace(" ", ""), text)


def clean_line(line):
    line = line.replace("\ufeff", " ").replace("\u2060", " ").replace("\xa0", " ")
    line = re.sub(r"^\s*\d+\s*[.)](?=\s|$)\s*", "", line.strip())
    line = normalize_number_separators(line)
    line = CURRENCY_RE.sub("", line)
    return re.sub(r"\s+", " ", line).strip()


def is_header(line):
    normalized = re.sub(r"[^\w]+", " ", line.lower(), flags=re.UNICODE).strip()
    return normalized in {"tortikipirogi", "tortikipirogi список"} or VENUE_HEADER_RE.match(line) is not None


def extract_venue_header(line):
    """Return a venue name from a dated price-list header, if present."""
    match = VENUE_HEADER_RE.match(clean_line(line))
    if not match:
        return None
    return match.group("store").strip(" .:-") or None


def extract_quantity(text):
    quantity = 1
    quantity_unit = None

    def replace(match):
        nonlocal quantity, quantity_unit
        quantity = int(match.group("qty"))
        unit = match.group("unit").lower()
        quantity_unit = "пор" if unit.startswith("пор") else "шт"
        return " "

    cleaned = QUANTITY_RE.sub(replace, text)
    cleaned = re.sub(r"\(\s*\)", " ", cleaned)
    cleaned = re.sub(r"\(\s*в\s+наличии\s*\)", " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" ,;-"), quantity, quantity_unit


def parse_line(line, store_name=STORE_NAME, coffi_discount_pct=COFFI_DEFAULT_DISCOUNT_PCT):
    """Return a parsed line or an error card fragment."""
    raw_line = line.strip()
    text = clean_line(raw_line).rstrip(".")
    if not text or SEPARATOR_RE.match(text) or is_header(text):
        return None

    text, quantity, quantity_unit = extract_quantity(text)

    if is_coffi_store(store_name):
        quantity_price = re.fullmatch(
            r"(?P<name>.+?)\s+(?P<qty>\d+)\s*/\s*(?P<original>\d+)", text
        )
        if quantity_price:
            original = int(quantity_price["original"])
            price = round(original * (100 - coffi_discount_pct) / 100)
            parsed = make_parsed(
                quantity_price["name"].strip(), price, original,
                int(quantity_price["qty"]), "шт", assumed_discount=True,
            )
            if parsed["qty"] <= 0:
                parsed["reviewReasons"].append("количество должно быть больше нуля")
            return parsed

    # Format 3: discounted price + "вместо" + original price.
    # The sale price may follow a dash, including after a cake weight range.
    reversed_explicit = re.match(
        r"^(?P<name>.+?)(?:\s*[-–—]\s*|\s+)(?P<price>\d+)\s+вместо\s+(?P<original>\d+)(?:\s|$)",
        text,
        re.IGNORECASE,
    )
    if reversed_explicit:
        name = reversed_explicit.group("name").strip(" ,;-«»")
        price = int(reversed_explicit.group("price"))
        original = int(reversed_explicit.group("original"))
        if not name:
            return {"rawLine": raw_line, "error": "не нашли название товара", "reviewReasons": ["не распознан формат строки"]}
        return make_parsed(name, price, original, quantity, quantity_unit, assumed_discount=False)

    # Format 2: name + original price + "со скидкой" + discounted price.
    explicit = re.match(
        r"^(?P<name>.+?)\s+(?P<original>\d+)\s*,?\s*со\s+скидкой\s+(?P<price>\d+)(?:\s|$)",
        text,
        re.IGNORECASE,
    )
    if explicit:
        name = explicit.group("name").strip(" ,;-«»")
        original = int(explicit.group("original"))
        price = int(explicit.group("price"))
        if not name:
            return {"rawLine": raw_line, "error": "не нашли название товара", "reviewReasons": ["не распознан формат строки"]}
        return make_parsed(name, price, original, quantity, quantity_unit, assumed_discount=False)

    # Format 1: split on the final dash, so hyphens inside names survive.
    short = re.match(r"^(?P<name>.+?)[\s]*-[\s]*(?P<price>\d+)$", text)
    if short:
        name = short.group("name").strip(" ,;-«»")
        price = int(short.group("price"))
        if not name:
            return {"rawLine": raw_line, "error": "не нашли название товара", "reviewReasons": ["не распознан формат строки"]}
        original = round(price / (1 - DEFAULT_DISCOUNT_PCT / 100))
        return make_parsed(name, price, original, quantity, quantity_unit, assumed_discount=True)

    return {
        "rawLine": raw_line,
        "error": "не распознан формат строки: ожидается 'Название-цена', 'Название оригинал, со скидкой цена' или 'Название цена вместо оригинала'",
        "reviewReasons": ["не распознан формат строки"],
    }


def make_parsed(name, price, original, quantity, quantity_unit, assumed_discount):
    reasons = []
    if original <= 0 or price <= 0:
        reasons.append("цена должна быть больше нуля")
    if price > original:
        reasons.append("скидочная цена выше оригинальной")
    return {
        "name": name,
        "price": price,
        "originalPrice": original,
        "qty": quantity,
        "qtyUnit": quantity_unit,
        "assumedDiscount": assumed_discount,
        "reviewReasons": reasons,
    }


def build_card(parsed, expiry_days=DEFAULT_EXPIRY_DAYS, store_name=STORE_NAME):
    price = parsed["price"]
    original = parsed["originalPrice"]
    discount = round((1 - price / original) * 100) if original else 0
    reasons = list(dict.fromkeys(parsed.get("reviewReasons", [])))
    expiry = (datetime.date.today() + datetime.timedelta(days=expiry_days)).isoformat() + "T21:00:00"
    coffi_store = is_coffi_store(store_name)
    image = None if coffi_store else image_for_product(parsed["name"])
    return {
        "storeName": store_name,
        "storeId": None,
        "rawLine_name": parsed["name"],
        "matchedCanonical": None,
        "matchScore": 1.0,
        "sizeDetected": None,
        "name": parsed["name"],
        "description": "",
        "price": price,
        "originalPrice": original,
        "discountPercentage": discount,
        "assumedDiscount": parsed.get("assumedDiscount", False),
        "assumedFromCatalog": False,
        "stockQuantity": parsed.get("qty", 1),
        "categoryName": "Кофейня" if coffi_store else CATEGORY_NAME,
        "images": [image] if image else [],
        "expiryDate": expiry,
        "status": STATUS,
        "reviewReasons": reasons,
        "needsReview": bool(reasons),
    }


def process(raw_text, expiry_days=DEFAULT_EXPIRY_DAYS, store_name=None):
    """Parse a message, optionally forcing one venue name for every card.

    A name supplied by the UI takes precedence over names embedded in a
    message header. Without it, the historical header-based behavior remains.
    """
    results = []
    selected_store_name = str(store_name or "").strip() or None
    current_store_name = selected_store_name or STORE_NAME
    coffi_discount_pct = COFFI_DEFAULT_DISCOUNT_PCT
    lines = html.unescape(raw_text).splitlines()
    has_boxes = any(BOX_HEADER_RE.fullmatch(clean_box_line(line)) for line in lines)
    box = None

    def flush_box():
        nonlocal box
        if box is not None:
            results.append(build_box_card(box, expiry_days))
            box = None

    for line in lines:
        if COFFI_HEADER_RE.fullmatch(clean_line(line)):
            flush_box()
            if selected_store_name is None:
                current_store_name = clean_line(line)
                coffi_discount_pct = COFFI_DEFAULT_DISCOUNT_PCT
            continue
        venue = extract_venue_header(line)
        if venue:
            flush_box()
            if selected_store_name is None:
                current_store_name = venue
                coffi_discount_pct = COFFI_DEFAULT_DISCOUNT_PCT
            continue
        if is_coffi_store(current_store_name) and re.fullmatch(r"сегодняшнее:?", clean_line(line), re.IGNORECASE):
            coffi_discount_pct = COFFI_TODAY_DISCOUNT_PCT
            continue
        if has_boxes:
            text = clean_box_line(line)
            if not text or re.match(r"^добрый\s+вечер\b", text, re.IGNORECASE):
                continue
            point = BOX_POINT_HEADERS.get(text.lower())
            if point:
                flush_box()
                if selected_store_name is None:
                    current_store_name = point
                continue
            priced_heading = PRICED_BOX_HEADER_RE.fullmatch(text)
            if priced_heading:
                flush_box()
                box = {
                    "name": f"Бокс {priced_heading['number']}",
                    "store": current_store_name, "components": [],
                    "description": [], "total": None,
                    "price": int(priced_heading["price"]), "reasons": [],
                }
                continue
            heading = BOX_HEADER_RE.fullmatch(text)
            if heading:
                flush_box()
                box = {
                    "name": f"Бокс №{heading['number']} — {heading['title']}",
                    "store": current_store_name, "components": [],
                    "description": [], "total": None, "price": None, "reasons": [],
                }
                continue
            if box is not None:
                if box["price"] is not None:
                    component = BOX_QUANTITY_RE.fullmatch(text)
                    if component:
                        name = component["name"].strip()
                        quantity = int(component["qty"])
                        unit = component["unit"]
                        box["components"].append((name, quantity))
                        box["description"].append(f"{name} — {quantity}" + (f" {unit}." if unit else ""))
                    else:
                        box["description"].append(line.strip())
                        box["reasons"].append(f"не распознана строка состава: {line.strip()}")
                    continue
                total = BOX_TOTAL_RE.fullmatch(text)
                if total:
                    box["total"] = int(total["price"])
                    flush_box()
                    continue
                component = BOX_COMPONENT_RE.fullmatch(text)
                if component:
                    name = component["name"].strip()
                    price = int(component["price"])
                    box["components"].append((name, price))
                    box["description"].append(f"{name} — {price} ₸")
                else:
                    box["description"].append(line.strip())
                    box["reasons"].append(f"не распознана строка состава: {line.strip()}")
                continue
        parsed = parse_line(line, store_name=current_store_name, coffi_discount_pct=coffi_discount_pct)
        if parsed is None:
            continue
        if parsed.get("error"):
            results.append(
                {
                    "storeName": current_store_name,
                    "rawLine": parsed["rawLine"],
                    "needsReview": True,
                    "reviewReasons": parsed.get("reviewReasons", []),
                    "error": parsed["error"],
                }
            )
        else:
            card = build_card(parsed, expiry_days, store_name=current_store_name)
            card["rawLine_name"] = parsed["name"]
            results.append(card)
    flush_box()
    return results


if __name__ == "__main__":
    import json
    import sys

    text = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding="utf-8").read()
    print(json.dumps(process(text), ensure_ascii=False, indent=2))
