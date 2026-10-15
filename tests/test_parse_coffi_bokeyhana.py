import unittest
from unittest.mock import patch

from parse_tortikipirogi import process
from server import upload_cards


SAMPLE = (
    "Клаб сэндвич с курицей 1/1490\n"
    "Бейгл с курицей 1/1890\n"
    "Паноццо с говядиной 1/1890\n"
    "Паноццо хот дог 1/1890\n"
    "Френч дог кетчуп 1/1500\n"
    "Бриошь с индейкой 2/1790\n"
    "Обед мясо по тайски с рисом 1/1990\n"
    "Обед пенне арабьята с курицей средней остроты 2/1990"
)


class CoffiCrmClient:
    def __init__(self, base_url, email, password):
        pass

    def login(self):
        pass

    def get_categories(self):
        return [{"id": 2, "name": "Кофейня"}, {"id": 7, "name": "Кондитерские изделия"}]

    def get_stores(self):
        return [{"id": 10, "name": "Coffi | Бокейхана 10"}]


class CoffiBokeyhanaParserTest(unittest.TestCase):
    def test_quantity_slash_original_price_creates_eight_coffi_cards(self):
        cards = process(SAMPLE, store_name="Coffi | Бокейхана 10")

        self.assertEqual(
            [(card.get("name"), card.get("stockQuantity"), card.get("price"), card.get("originalPrice")) for card in cards],
            [
                ("Клаб сэндвич с курицей", 1, 596, 1490),
                ("Бейгл с курицей", 1, 756, 1890),
                ("Паноццо с говядиной", 1, 756, 1890),
                ("Паноццо хот дог", 1, 756, 1890),
                ("Френч дог кетчуп", 1, 600, 1500),
                ("Бриошь с индейкой", 2, 716, 1790),
                ("Обед мясо по тайски с рисом", 1, 796, 1990),
                ("Обед пенне арабьята с курицей средней остроты", 2, 796, 1990),
            ],
        )
        self.assertTrue(all(card["storeName"] == "Coffi | Бокейхана 10" for card in cards))
        self.assertTrue(all(card["categoryName"] == "Кофейня" for card in cards))
        self.assertTrue(all(card["discountPercentage"] == 60 for card in cards))
        self.assertTrue(all(not card["needsReview"] and card["images"] == [] for card in cards))

    def test_today_marker_uses_fifty_percent_and_other_formats_still_work(self):
        cards = process(
            "Сегодняшнее\nБейгл с курицей 1/1890\n"
            "Круассан с семгой 1800, со скидкой 1440",
            store_name="Coffi | Бокейхана 10",
        )

        self.assertEqual([card.get("price") for card in cards], [945, 1440])
        self.assertEqual([card.get("discountPercentage") for card in cards], [50, 20])
        self.assertTrue(all(not card["needsReview"] for card in cards))

    def test_message_header_selects_coffi_and_slash_format_is_partner_specific(self):
        cards = process("Coffi | Бокейхана 10\nКлаб сэндвич с курицей 1/1490")
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["storeName"], "Coffi | Бокейхана 10")
        self.assertEqual(cards[0]["price"], 596)
        self.assertTrue(process("Клаб сэндвич с курицей 1/1490")[0]["needsReview"])

    def test_coffi_does_not_use_tortikipirogi_product_photos(self):
        card = process("Круассан с семгой 1/1800", store_name="Coffi | Бокейхана 10")[0]
        self.assertEqual(card["images"], [])

    def test_zero_quantity_requires_review(self):
        card = process("Бейгл с курицей 0/1890", store_name="Coffi | Бокейхана 10")[0]
        self.assertTrue(card["needsReview"])

    def test_coffi_category_and_store_reach_crm_dry_run(self):
        card = process(SAMPLE, store_name="Coffi | Бокейхана 10")[0]
        with patch("server.CrmClient", CoffiCrmClient):
            report = upload_cards(
                [card], dry_run=True,
                config_overrides={"category_name": "Кондитерские изделия"},
            )

        self.assertEqual(report["summary"]["ok"], 1)
        self.assertEqual(report["report"][0]["payload"]["storeId"], 10)
        self.assertEqual(report["report"][0]["payload"]["categoryId"], 2)
        self.assertEqual(report["report"][0]["payload"]["price"], 596)
        self.assertEqual(report["report"][0]["payload"]["originalPrice"], 1490)


if __name__ == "__main__":
    unittest.main()
