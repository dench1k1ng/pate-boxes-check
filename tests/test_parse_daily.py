import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parse_daily import process  # noqa: E402


class ParseDailyHeavyInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ROOT / "catalog_paste.json", encoding="utf-8") as f:
            cls.catalog = json.load(f)

    def parse_one(self, body):
        out = process(body, self.catalog)
        self.assertEqual(len(out), 1)
        return out[0]

    def test_quantity_before_price(self):
        card = self.parse_one("Пате Ишим\nкольцо творожное 1 шт 1020 тг вместо 1700")
        self.assertEqual(card["matchedCanonical"], "Кольца творожные")
        self.assertEqual(card["price"], 1020)
        self.assertEqual(card["originalPrice"], 1700)
        self.assertEqual(card["stockQuantity"], 1)
        self.assertFalse(card["needsReview"])

    def test_catalog_price_from_discount_header(self):
        card = self.parse_one("Пате Ишим: 40%\nулитка 2 шт")
        self.assertEqual(card["matchedCanonical"], "Улитка с шоколадом")
        self.assertEqual(card["price"], 870)
        self.assertEqual(card["originalPrice"], 1450)
        self.assertEqual(card["stockQuantity"], 2)
        self.assertTrue(card["assumedFromCatalog"])
        self.assertFalse(card["needsReview"])

    def test_portion_unit_guides_catalog_match(self):
        card = self.parse_one("Пате Ишим: 40%\nфисташка малина 1 пор")
        self.assertEqual(card["matchedCanonical"], "Фисташковый пирог с малиной")
        self.assertEqual(card["sizeDetected"], "порция")
        self.assertEqual(card["price"], 1380)
        self.assertFalse(card["needsReview"])

    def test_slash_variant_splits_into_two_cards(self):
        out = process(
            "Пате Толе би\n"
            "Безглютеновая галета с нектарином макси/мини 3480/1590 вместо 5800/2650",
            self.catalog,
        )
        self.assertEqual(len(out), 2)
        self.assertEqual([x["price"] for x in out], [3480, 1590])
        self.assertEqual([x["originalPrice"] for x in out], [5800, 2650])
        self.assertTrue(all(not x["needsReview"] for x in out))


if __name__ == "__main__":
    unittest.main()
