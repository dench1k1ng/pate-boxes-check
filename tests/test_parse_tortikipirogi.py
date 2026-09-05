import unittest
from unittest.mock import patch

from parse_tortikipirogi import process
from server import upload_cards


class FakeCrmClient:
    def __init__(self, base_url, email, password):
        self.created = []

    def login(self):
        pass

    def get_categories(self):
        return [{"id": 7, "name": "Кондитерские изделия"}]

    def get_stores(self):
        return [{"id": 42, "name": "Tortikipirogi"}]

    def create_product(self, payload):
        self.created.append(payload)

        class Response:
            status_code = 201

            @staticmethod
            def json():
                return {"id": 123}

        return Response()


class TortikipirogiParserTest(unittest.TestCase):
    def test_all_short_format_items_keep_internal_hyphens_and_slashes(self):
        text = "\n".join([
            "Трайфл медовый-760",
            "Трайфл красный бархат-760",
            "Трайфл рафаэлло-800",
            "Трайфл фисташка-малина-960",
            "Шок-пломбир-800",
            "Шой-банан-800",
            "Нарезное пирожное карамельная молочная девочка-720",
            "Нарезное пирожное молочная девочка -720",
            "Картошка-320",
            "Медовик пирожное-720",
            "Наполеон пирожное-720",
            "Творожный пирог-4000",
            "Творожный пирог мини-680",
            "Баннофи пай-4800",
            "Баннофи пай мини-720",
            "Рогалики со сгущенкой-2800",
            "Блины со сгущенкой-280",
            "Пицци мини-560",
            "Синнабон-800",
            "Киш Лорен-4000",
            "Киш Лорен мини-760",
            "Самса курица/мясо-320",
            "Пирожки с картошкой-320",
            "Блины с мясом и грибами-320",
            "Панини с семгой-1580",
            "Панини с курицей-1400",
            "Круассан с курицей-1400",
            "Круассан с семгой-1440",
        ])
        cards = process(text)
        self.assertEqual(len(cards), 28)
        self.assertTrue(all(not card["needsReview"] for card in cards))
        self.assertEqual(cards[4]["name"], "Шок-пломбир")
        self.assertEqual(cards[21]["name"], "Самса курица/мясо")
        self.assertEqual(cards[0]["originalPrice"], 950)
        self.assertEqual(cards[0]["discountPercentage"], 20)

    def test_explicit_format(self):
        cards = process(
            "Круассан с семгой 1800, со скидкой 1440\n"
            "Круассан с курицей 1750, со скидкой 1400\n"
            "Панини с курицей 1750, со скидкой 1400"
        )
        self.assertEqual([(c["originalPrice"], c["price"], c["discountPercentage"]) for c in cards], [
            (1800, 1440, 20),
            (1750, 1400, 20),
            (1750, 1400, 20),
        ])

    def test_mixed_formats_and_quantity(self):
        cards = process(
            "Tortikipirogi\n"
            "Шок-пломбир-800\n"
            "Панини с курицей 2 шт-1400\n"
            "Круассан с семгой 1800, со скидкой 1440"
        )
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[1]["stockQuantity"], 2)
        self.assertEqual(cards[1]["name"], "Панини с курицей")
        self.assertTrue(all(card["storeName"] == "Tortikipirogi" for card in cards))

    def test_bad_line_is_reviewed_and_not_uploaded_without_confirmation(self):
        cards = process("Трайфл медовый-760\nСтрока без цены")
        self.assertTrue(cards[1]["needsReview"])
        with patch("server.CrmClient", FakeCrmClient):
            report = upload_cards(
                cards,
                dry_run=True,
                config_overrides={
                    "category_name": "Кондитерские изделия",
                    "store_aliases": {"tortikipirogi": "Tortikipirogi"},
                },
            )
        self.assertEqual(report["summary"]["ok"], 1)
        self.assertEqual(report["summary"]["skipped"], 1)
        self.assertEqual(report["report"][1]["reason"], "не распознана строка")

    def test_dry_run_payload_has_crm_defaults_and_no_images(self):
        card = process("Круассан с семгой 1800, со скидкой 1440")[0]
        with patch("server.CrmClient", FakeCrmClient):
            report = upload_cards(
                [card],
                dry_run=True,
                config_overrides={
                    "category_name": "Кондитерские изделия",
                    "store_aliases": {"tortikipirogi": "Tortikipirogi"},
                },
            )
        payload = report["report"][0]["payload"]
        self.assertEqual(payload["storeId"], 42)
        self.assertEqual(payload["categoryId"], 7)
        self.assertEqual(payload["price"], 1440)
        self.assertEqual(payload["originalPrice"], 1800)
        self.assertEqual(payload["stockQuantity"], 1)
        self.assertEqual(payload["images"], [])
        self.assertEqual(payload["status"], "AVAILABLE")


if __name__ == "__main__":
    unittest.main()
