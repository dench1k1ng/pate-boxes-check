import unittest
from unittest.mock import patch

from parse_mamin_hleb import process
from server import upload_cards


MESSAGE = """Аспан базар
Сладкий бокс
Мини творожник 2
Мини шарлотка 2
Маковик 3
Мини сметанник 1

Сладкий бокс 2
Мини сметанник 3
Ватрушка с творогом 2
Лакомка арахис 1
Маковик 1
Лакомка банан 1
Багет с изюмом 1

Сытный бокс 1
Пирог курица картошка 1
Ашлама 1
Сосиски в тесте 1

Сытный бокс 2
Хот дог 2
Самса с мясом 2
Сосиски в тесте 3

Сытный бокс 3
Бутерброд 2
Ашлама 1
Самса с курицей 2
Пирожок яйцо лук 1
Пирог с картошкой 1

Сытный бокс 4
Хачапури 3
Багет провансаль с ветчиной 2
Пирожок с картошкой 3

Сытный бокс 5
Элеш 1
Хачапури с сыром 3
Сосиски в тесте 2
Багет провансаль с ветчиной 1"""


class FakeCrmClient:
    def __init__(self, base_url, email, password):
        self.created = []

    def login(self):
        pass

    def get_categories(self):
        return [{"id": 2, "name": "Кофейня"}, {"id": 3, "name": "Пекарня"}]

    def get_stores(self):
        return [
            {"id": 3, "name": "Мамин хлеб | Абая 8"},
            {"id": 4, "name": "Мамин хлеб | Аспан базар"},
            {"id": 8, "name": "Мамин хлеб | Ауэзова, 42"},
            {"id": 7, "name": "Royalty Coffee | Сыганак 3"},
        ]

    def create_product(self, payload):
        self.created.append(payload)

        class Response:
            status_code = 201

            @staticmethod
            def json():
                return {"id": 123}

        return Response()


class MaminHlebParserTest(unittest.TestCase):
    def test_boxes_become_fixed_price_cards_with_composition(self):
        cards = process(MESSAGE)

        self.assertEqual(len(cards), 7)
        self.assertEqual(cards[0]["name"], "Сладкий бокс")
        self.assertEqual(cards[-1]["name"], "Сытный бокс 5")
        self.assertTrue(all(card["storeName"] == "Мамин хлеб | Аспан базар" for card in cards))
        self.assertTrue(all(card["price"] == 1725 for card in cards))
        self.assertTrue(all(card["originalPrice"] == 3450 for card in cards))
        self.assertTrue(all(card["discountPercentage"] == 50 for card in cards))
        self.assertTrue(all(card["categoryName"] == "Пекарня" for card in cards))
        self.assertIn("Мини творожник — 2", cards[0]["description"])

    def test_point_header_switches_store(self):
        cards = process(
            "Аспан базар\nСладкий бокс\nМаковик 3\n"
            "Абая 8\nСытный бокс 1\nАшлама 1"
        )

        self.assertEqual(
            [card["storeName"] for card in cards],
            ["Мамин хлеб | Аспан базар", "Мамин хлеб | Абая 8"],
        )

    def test_aspan_bazar_resolves_to_crm_store_4(self):
        card = process("Аспан базар\nСладкий бокс\nМаковик 3")[0]
        with patch("server.CrmClient", FakeCrmClient):
            report = upload_cards(
                [card],
                dry_run=True,
                config_overrides={
                    "category_name": "Пекарня",
                    "store_aliases": {"аспан базар": "Мамин хлеб | Аспан базар"},
                },
            )

        self.assertEqual(report["report"][0]["payload"]["storeId"], 4)
        self.assertEqual(report["report"][0]["payload"]["categoryId"], 3)

    def test_royalty_syganak_boxes_use_line_prices_and_coffee_store(self):
        cards = process(
            "Сыганак 3\n"
            "Бокс 1 - 1625 тг\n"
            "Круассан с курицей и карри - 1\n"
            "Бейгл с семгой - 1\n"
            "Бокс 2 - 1595 тг\n"
            "Круассан с курицей и карри - 1\n"
            "Цезарь с курицей - 1\n"
            "Бокс 6 - 1500 тг\n"
            "Орешки со сгущёнкой - 12"
        )

        self.assertEqual([card["name"] for card in cards], ["Бокс 1", "Бокс 2", "Бокс 6"])
        self.assertEqual([card["price"] for card in cards], [1625, 1595, 1500])
        self.assertEqual([card["originalPrice"] for card in cards], [3250, 3190, 3000])
        self.assertTrue(all(card["discountPercentage"] == 50 for card in cards))
        self.assertTrue(all(card["storeName"] == "Royalty Coffee | Сыганак 3" for card in cards))
        self.assertTrue(all(card["categoryName"] == "Кофейня" for card in cards))
        self.assertIn("Орешки со сгущёнкой — 12", cards[-1]["description"])

        with patch("server.CrmClient", FakeCrmClient):
            report = upload_cards(
                [cards[0]],
                dry_run=True,
                config_overrides={
                    "category_name": "Кофейня",
                    "store_aliases": {"сыганак 3": "Royalty Coffee | Сыганак 3"},
                },
            )
        self.assertEqual(report["report"][0]["payload"]["storeId"], 7)
        self.assertEqual(report["report"][0]["payload"]["categoryId"], 2)

    def test_discounted_price_rule_and_components_with_units(self):
        cards = process(
            "Сыганак 3\n"
            "Бокс 1 - 1200\n"
            "Круассан - 1 шт\n"
            "Панини - 1 шт"
        )

        self.assertEqual(cards[0]["price"], 1200)
        self.assertEqual(cards[0]["originalPrice"], 2400)
        self.assertEqual(cards[0]["discountPercentage"], 50)
        self.assertIn("Круассан — 1", cards[0]["description"])
        self.assertIn("Панини — 1", cards[0]["description"])


if __name__ == "__main__":
    unittest.main()
