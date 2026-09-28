# -*- coding: utf-8 -*-
"""Parser for Mamin khleb box messages.

The message describes one or more boxes. Each box is published as one CRM
product at the discounted price of 1725 and original price of 3450; the lines
below its heading become the composition in the product description. Point
headings switch the CRM store.
"""
import datetime
import html
import re


PRICE = 1725
ORIGINAL_PRICE = 3450
CATEGORY_NAME = "Пекарня"
DEFAULT_STORE_NAME = "Мамин хлеб | Аспан базар"
DEFAULT_EXPIRY_DAYS = 1
STATUS = "AVAILABLE"
ROYALTY_STORE_NAME = "Royalty Coffee | Сыганак 3"
# Prices in the `Бокс N - цена` format are supplied as discounted prices.
# Keep this as a rule constant so the original-price policy can be changed
# without touching the parser flow.
PRICED_BOX_ORIGINAL_PRICE_MULTIPLIER = 2

POINT_ALIASES = {
    "аспан базар": "Мамин хлеб | Аспан базар",
    "мамин хлеб аспан базар": "Мамин хлеб | Аспан базар",
    "мамин хлеб | аспан базар": "Мамин хлеб | Аспан базар",
    "абая 8": "Мамин хлеб | Абая 8",
    "мамин хлеб абая 8": "Мамин хлеб | Абая 8",
    "мамин хлеб | абая 8": "Мамин хлеб | Абая 8",
    "ауэзова 42": "Мамин хлеб | Ауэзова, 42",
    "ауэзова, 42": "Мамин хлеб | Ауэзова, 42",
    "мамин хлеб ауэзова 42": "Мамин хлеб | Ауэзова, 42",
    "мамин хлеб | ауэзова 42": "Мамин хлеб | Ауэзова, 42",
    "сыганак 3": ROYALTY_STORE_NAME,
    "royalty coffee сыганак 3": ROYALTY_STORE_NAME,
    "royalty coffee | сыганак 3": ROYALTY_STORE_NAME,
}
BOX_RE = re.compile(r"^(?P<name>(?:сладкий|сытный)\s+бокс(?:\s+\d+)?)$", re.IGNORECASE)
PRICED_BOX_RE = re.compile(
    r"^(?P<name>бокс\s+\d+)\s*-\s*(?P<price>\d+)\s*(?:тг|тенге|₸)?$",
    re.IGNORECASE,
)
COMPONENT_RE = re.compile(
    r"^(?P<name>.+?)(?:\s*-\s*|\s+)(?P<qty>\d+)"
    r"(?:\s*(?:шт|штуки|штук|порция|порции))?$",
    re.IGNORECASE,
)
SEPARATOR_RE = re.compile(r"^[-=_*]{3,}\s*$")


def clean_line(line):
    value = html.unescape(line).replace("\ufeff", " ").replace("\u2060", " ")
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalize_header(line):
    return re.sub(r"[^\w]+", " ", clean_line(line).lower(), flags=re.UNICODE).strip()


def extract_point(line):
    return POINT_ALIASES.get(normalize_header(line))


def parse_component(line):
    match = COMPONENT_RE.match(clean_line(line))
    if not match:
        return None
    name = match.group("name").strip(" .:-")
    if not name:
        return None
    return name, int(match.group("qty"))


def build_card(box_name, components, store_name, expiry_days, price, original_price, discount, category_name):
    expiry = (datetime.date.today() + datetime.timedelta(days=expiry_days)).isoformat() + "T21:00:00"
    composition = "\n".join(f"{name} — {quantity}" for name, quantity in components)
    return {
        "storeName": store_name,
        "storeId": None,
        "rawLine_name": box_name,
        "matchedCanonical": None,
        "matchScore": 1.0,
        "sizeDetected": None,
        "name": box_name,
        "description": f"Состав:\n{composition}" if composition else "",
        "price": price,
        "originalPrice": original_price,
        "discountPercentage": discount,
        "assumedDiscount": False,
        "assumedFromCatalog": False,
        "stockQuantity": 1,
        "categoryName": category_name,
        "images": [],
        "expiryDate": expiry,
        "status": STATUS,
        "reviewReasons": [],
        "needsReview": False,
    }


def process(raw_text, expiry_days=DEFAULT_EXPIRY_DAYS, store_name=None):
    """Parse box sections and switch store when a known point heading appears."""
    results = []
    current_store = str(store_name or "").strip() or DEFAULT_STORE_NAME
    current_price = PRICE
    current_original_price = ORIGINAL_PRICE
    current_discount = 50
    current_category = CATEGORY_NAME
    current_box = None
    components = []

    def apply_store_profile():
        nonlocal current_price, current_original_price, current_discount, current_category
        if current_store == ROYALTY_STORE_NAME:
            current_price = PRICE
            current_original_price = PRICE
            current_discount = 0
            current_category = "Кофейня"
        else:
            current_price = PRICE
            current_original_price = ORIGINAL_PRICE
            current_discount = 50
            current_category = CATEGORY_NAME

    apply_store_profile()

    def flush_box():
        nonlocal current_box, components
        if current_box:
            results.append(
                build_card(
                    current_box,
                    components,
                    current_store,
                    expiry_days,
                    current_price,
                    current_original_price,
                    current_discount,
                    current_category,
                )
            )
        current_box = None
        components = []

    for raw_line in raw_text.splitlines():
        line = clean_line(raw_line)
        if not line or SEPARATOR_RE.match(line) or line.lower().startswith("добрый вечер"):
            continue

        point = extract_point(line)
        if point:
            flush_box()
            current_store = point
            apply_store_profile()
            continue

        priced_box = PRICED_BOX_RE.match(line)
        if priced_box:
            flush_box()
            current_box = priced_box.group("name").strip()
            current_price = int(priced_box.group("price"))
            current_original_price = round(
                current_price * PRICED_BOX_ORIGINAL_PRICE_MULTIPLIER
            )
            current_discount = round(
                (1 - current_price / current_original_price) * 100
            )
            continue

        box = BOX_RE.match(line)
        if box:
            flush_box()
            current_box = box.group("name").strip()
            apply_store_profile()
            continue

        if current_box:
            component = parse_component(line)
            if component:
                components.append(component)

    flush_box()
    return results


if __name__ == "__main__":
    import json
    import sys

    text = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding="utf-8").read()
    print(json.dumps(process(text), ensure_ascii=False, indent=2))
