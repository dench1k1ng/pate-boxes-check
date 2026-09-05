# -*- coding: utf-8 -*-
"""Parser for Tortikipirogi's simple daily discount lists.

Supported formats (both may appear in one message)::

    Трайфл медовый-760
    Круассан с семгой 1800, со скидкой 1440

Unlike the Pâté parser, this parser deliberately does not use a product
catalogue or rename product names.  Every successfully parsed line becomes a
CRM-ready card for the Tortikipirogi store.
"""
import datetime
import re


STORE_NAME = "Tortikipirogi"
CATEGORY_NAME = "Кондитерские изделия"
DEFAULT_DISCOUNT_PCT = 20
DEFAULT_EXPIRY_DAYS = 1
STATUS = "AVAILABLE"

SEPARATOR_RE = re.compile(r"^[-=_*]{3,}\s*$")
QUANTITY_RE = re.compile(
    r"\b(?P<qty>\d+)\s*(?P<unit>шт(?:\.?|ук)?|штук|порц(?:ия|ии|ию|ий)?|пор|уп(?:ак(?:овк[аи])?)?)\b",
    re.IGNORECASE,
)
NUMBER_WITH_SEPARATOR_RE = re.compile(r"(?<!\w)\d{1,3}(?:[ .]\d{3})+(?!\w)")
CURRENCY_RE = re.compile(r"(?<=\d)\s*(?:тенге|тг|₸|т)(?=\s|$|[,.;])", re.IGNORECASE)


def normalize_number_separators(text):
    return NUMBER_WITH_SEPARATOR_RE.sub(lambda m: m.group(0).replace(".", "").replace(" ", ""), text)


def clean_line(line):
    line = line.replace("\ufeff", " ").replace("\u2060", " ").replace("\xa0", " ")
    line = re.sub(r"^\s*\d+\s*[.)]\s*", "", line.strip())
    line = normalize_number_separators(line)
    line = CURRENCY_RE.sub("", line)
    return re.sub(r"\s+", " ", line).strip()


def is_header(line):
    normalized = re.sub(r"[^\w]+", " ", line.lower(), flags=re.UNICODE).strip()
    return normalized in {"tortikipirogi", "tortikipirogi список"}


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
    return re.sub(r"\s+", " ", cleaned).strip(" ,;-"), quantity, quantity_unit


def parse_line(line):
    """Return a parsed line or an error card fragment."""
    raw_line = line.strip()
    text = clean_line(raw_line).rstrip(".")
    if not text or SEPARATOR_RE.match(text) or is_header(text):
        return None

    text, quantity, quantity_unit = extract_quantity(text)

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
        "error": "не распознан формат строки: ожидается 'Название-цена' или 'Название оригинал, со скидкой цена'",
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


def build_card(parsed, expiry_days=DEFAULT_EXPIRY_DAYS):
    price = parsed["price"]
    original = parsed["originalPrice"]
    discount = round((1 - price / original) * 100) if original else 0
    reasons = list(dict.fromkeys(parsed.get("reviewReasons", [])))
    expiry = (datetime.date.today() + datetime.timedelta(days=expiry_days)).isoformat() + "T21:00:00"
    return {
        "storeName": STORE_NAME,
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
        "categoryName": CATEGORY_NAME,
        "images": [],
        "expiryDate": expiry,
        "status": STATUS,
        "reviewReasons": reasons,
        "needsReview": bool(reasons),
    }


def process(raw_text, expiry_days=DEFAULT_EXPIRY_DAYS):
    results = []
    for line in raw_text.splitlines():
        parsed = parse_line(line)
        if parsed is None:
            continue
        if parsed.get("error"):
            results.append(
                {
                    "storeName": STORE_NAME,
                    "rawLine": parsed["rawLine"],
                    "needsReview": True,
                    "reviewReasons": parsed.get("reviewReasons", []),
                    "error": parsed["error"],
                }
            )
        else:
            card = build_card(parsed, expiry_days)
            card["rawLine_name"] = parsed["name"]
            results.append(card)
    return results


if __name__ == "__main__":
    import json
    import sys

    text = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding="utf-8").read()
    print(json.dumps(process(text), ensure_ascii=False, indent=2))
