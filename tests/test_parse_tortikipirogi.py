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
        return [
            {"id": 42, "name": "Tortikipirogi"},
            {"id": 43, "name": "Жаннур"},
            {"id": 48, "name": "KULINAR&CA"},
        ]

    def create_product(self, payload):
        self.created.append(payload)

        class Response:
            status_code = 201

            @staticmethod
            def json():
                return {"id": 123}

        return Response()


class TortikipirogiParserTest(unittest.TestCase):
    def test_venue_header_and_price_instead_original_with_stock(self):
        cards = process(
            "27.09 Жаннур. Цена за 1 шт\n"
            "Клаб сэндвич с курицей 665 вместо 950 (в наличии 2 шт)\n"
            "Самса с мясом 315 вместо 450 (в наличии 4 шт)\n"
            "Самса с курицей 245 вместо 350 (в наличии 4 шт)\n"
            "Чикен ролл 735 вместо 1050 (в наличии 1 шт)\n"
            "Сандо 910 вместо 1300 (в наличии 1 шт)\n"
            "Мясной пирог 3150 вместо 4500 (в наличии 2 шт)\n"
            "Пирог сметанный с черникой 2100 вместо 3000 (в наличии 1 шт)\n"
            "Пирог яблочный 1750 вместо 2500 (в наличии 2 шт)\n"
            "Молочная девочка 840 вместо 1200 (в наличии 1 шт)\n"
            "Блинный 840 вместо 1200 (в наличии 1 шт)\n"
            "Медовик 840 вместо 1200 (в наличии 2 шт)\n"
            "Морковный 840 вместо 1200 (в наличии 2 шт)\n"
            "Шоколадный 840 вместо 1200 (в наличии 1 шт)\n"
            "Сникерс 840 вместо 1200 (в наличии 2 шт)\n"
            "Вупи пай 490 вместо 700 (в наличии 5 шт)\n"
            "Испанский чизкейк 840 вместо 1200 (в наличии 1 шт)\n"
            "Испанский чизкейк целый 4550 вместо 6500 (в наличии 1 шт)\n"
            "Малиновый чизкейк 840 вместо 1200 (в наличии 2 шт)\n"
            "Тирамису черничный 840 вместо 1200 (в наличии 3 шт)\n"
            "Тирамису крем брюле 840 вместо 1200 (в наличии 6 шт)\n"
            "Наполеон целый 5110 вместо 7300 (в наличии 1 шт)\n"
            "Шоколадный целый 5810 вместо 8300 (в наличии 1 шт)\n"
            "Корпусный десерт кофейное зерно 700 вместо 1000 ( в наличии 6 шт)\n"
            "Корпусный десерт малина 700 вместо 1000 (в наличии 4 шт)\n"
            "Корпусный десерт черника 700 вместо 1000 ( в наличии 3 шт)\n"
            "Корпусный десерт лимон 700 вместо 1000 ( в наличии 3 шт)\n"
            "Тарталетки яблочная 315 вместо 450 (в наличии 2 шт)\n"
            "Тарталетка восточная 455 вместо 650 (в наличии 1 шт)"
        )

        self.assertEqual(len(cards), 28)
        self.assertTrue(all(card["storeName"] == "Жаннур" for card in cards))
        self.assertTrue(all(not card["needsReview"] for card in cards))
        self.assertEqual(
            [(cards[0]["price"], cards[0]["originalPrice"], cards[0]["stockQuantity"]),
             (cards[-1]["price"], cards[-1]["originalPrice"], cards[-1]["stockQuantity"])],
            [(665, 950, 2), (455, 650, 1)],
        )

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

    def test_explicit_store_name_overrides_message_header_for_all_cards(self):
        cards = process(
            "27.09 Жаннур. Цена за 1 шт\n"
            "Клаб сэндвич с курицей 665 вместо 950 (в наличии 2 шт)\n"
            "Самса с мясом 315 вместо 450 (в наличии 4 шт)",
            store_name="KULINAR&CA",
        )
        self.assertEqual([card["storeName"] for card in cards], ["KULINAR&CA", "KULINAR&CA"])

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

    def test_venue_from_header_resolves_to_matching_crm_store(self):
        card = process(
            "27.09 Жаннур. Цена за 1 шт\n"
            "Клаб сэндвич с курицей 665 вместо 950 (в наличии 2 шт)"
        )[0]
        with patch("server.CrmClient", FakeCrmClient):
            report = upload_cards(
                [card],
                dry_run=True,
                config_overrides={"category_name": "Кондитерские изделия"},
            )
        self.assertEqual(report["report"][0]["payload"]["storeId"], 43)
        self.assertEqual(report["report"][0]["storeMatch"]["name"], "Жаннур")

    def test_kulinar_name_resolves_to_crm_store_48(self):
        card = process("Медовик 840 вместо 1200", store_name="KULINAR&CA")[0]
        with patch("server.CrmClient", FakeCrmClient):
            report = upload_cards(
                [card],
                dry_run=True,
                config_overrides={
                    "category_name": "Кондитерские изделия",
                    "store_aliases": {"kulinar&ca": "KULINAR&CA"},
                },
            )
        self.assertEqual(report["report"][0]["payload"]["storeId"], 48)
        self.assertEqual(report["report"][0]["storeMatch"]["name"], "KULINAR&CA")


if __name__ == "__main__":
    unittest.main()
