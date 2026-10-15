import unittest

from parse_tortikipirogi import process


class PriceInsteadParserTest(unittest.TestCase):
    def test_hyphenated_sale_prices_with_cake_weight_and_stock(self):
        cards = process(
            "Круассан курица -1190 вместо 1700 (1шт)\n"
            "Панини курица-1225 вместо 1750 (1шт)\n"
            "Киш Лорен мини -665 вместо 950 (1шт)\n"
            "Киш Лорен-4000 вместо 5000 (1шт)\n"
            "Куриный пирог мини-630  вместо 900 (2шт)\n"
            "Куриный пирог-3500 вместо 5000 (1шт)\n"
            "Творожный мини-595 вместо 850 (4шт)\n"
            "Торт молочная девочка вес 1-1.3-7000 вместо 10000(1шт)\n"
            "Торт карамельная молочная девочка вес 1-1.3-7000 вместо 10000(1шт)"
        )

        self.assertEqual(
            [(card.get("name"), card.get("price"), card.get("originalPrice"), card.get("stockQuantity")) for card in cards],
            [
                ("Круассан курица", 1190, 1700, 1),
                ("Панини курица", 1225, 1750, 1),
                ("Киш Лорен мини", 665, 950, 1),
                ("Киш Лорен", 4000, 5000, 1),
                ("Куриный пирог мини", 630, 900, 2),
                ("Куриный пирог", 3500, 5000, 1),
                ("Творожный мини", 595, 850, 4),
                ("Торт молочная девочка вес 1-1.3", 7000, 10000, 1),
                ("Торт карамельная молочная девочка вес 1-1.3", 7000, 10000, 1),
            ],
        )
        self.assertTrue(all(not card["needsReview"] for card in cards))
        self.assertEqual([card["discountPercentage"] for card in cards], [30, 30, 30, 20, 30, 30, 30, 30, 30])

    def test_sale_price_format_coexists_with_short_explicit_and_box_formats(self):
        cards = process(
            "Шок-пломбир-800\n"
            "Торт молочная девочка вес 1-1.3-7000 вместо 10000(1шт)\n"
            "Бокс №1 — Сытный\n"
            "Круассан — 500 ₸\n"
            "Итого: 500 ₸\n"
            "Круассан с семгой 1800, со скидкой 1440"
        )

        self.assertEqual([card.get("name") for card in cards], [
            "Шок-пломбир", "Торт молочная девочка вес 1-1.3",
            "Бокс №1 — Сытный", "Круассан с семгой",
        ])
        self.assertEqual([card.get("price") for card in cards], [800, 7000, 500, 1440])
        self.assertTrue(all(not card["needsReview"] for card in cards))


if __name__ == "__main__":
    unittest.main()
