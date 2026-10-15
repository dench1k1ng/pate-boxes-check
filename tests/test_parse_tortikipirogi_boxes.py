from pathlib import Path
import unittest
from unittest.mock import patch

from parse_tortikipirogi import process
from server import upload_cards
from test_parse_tortikipirogi import FakeCrmClient


SAMPLE = (Path(__file__).parent / "fixtures" / "republic_boxes.txt").read_text(encoding="utf-8")


class NamedBoxParserTest(unittest.TestCase):
    def test_syganak_heading_and_priced_boxes_create_only_three_cards(self):
        cards = process(
            "Сыганак 3\n\n"
            "Бокс 1 - 1615 тг\n"
            "Панини с тунцом — 1 шт.\n"
            "Профитроли сливочные — 1 шт.\n\n"
            "Бокс 2 — 1150 тг\n"
            "Миндальный круассан — 1 шт.\n"
            "Арахисовый круассан — 1 шт.\n\n"
            "Бокс 3 — 1875 тг\n"
            "Фитбоул с лососем — 1 шт.\n"
            "Арахисовый круассан — 1 шт."
        )

        self.assertEqual([card["name"] for card in cards], ["Бокс 1", "Бокс 2", "Бокс 3"])
        self.assertEqual([card["price"] for card in cards], [1615, 1150, 1875])
        self.assertTrue(all(card["storeName"] == "Royalty Coffee | Сыганак 3" for card in cards))
        self.assertTrue(all(not card["needsReview"] for card in cards))

    def test_priced_boxes_with_component_quantities_need_no_total(self):
        cards = process(
            "Бокс 1 — 1 075 ₸\n"
            "Маффин чиз — 1 шт.\n"
            "Френч-дог классический — 1 шт.\n\n"
            "Бокс 2 — 825 ₸\n"
            "Салат Цезарь — 1 шт.\n\n"
            "Бокс 3 — 1 050 ₸\n"
            "Булгур — 1 шт.",
            store_name='Royalty Coffee | ТРЦ "Жаннур"',
        )

        self.assertEqual([card["name"] for card in cards], ["Бокс 1", "Бокс 2", "Бокс 3"])
        self.assertEqual([card["price"] for card in cards], [1075, 825, 1050])
        self.assertEqual([card["originalPrice"] for card in cards], [2150, 1650, 2100])
        self.assertEqual([card["discountPercentage"] for card in cards], [50, 50, 50])
        self.assertEqual([card["description"] for card in cards], [
            "Состав:\nМаффин чиз — 1 шт.\nФренч-дог классический — 1 шт.",
            "Состав:\nСалат Цезарь — 1 шт.",
            "Состав:\nБулгур — 1 шт.",
        ])
        self.assertTrue(all(card["storeName"] == 'Royalty Coffee | ТРЦ "Жаннур"' for card in cards))
        self.assertTrue(all(not card["needsReview"] for card in cards))

    def test_complete_message_produces_eight_boxes_with_composition_and_sale_prices(self):
        cards = process(SAMPLE, store_name="Tortikipirogi")
        self.assertEqual(len(cards), 8)
        self.assertEqual([c["price"] for c in cards], [1750, 1270, 1575, 1535, 1425, 1800, 1520, 1960])
        self.assertEqual([c["name"] for c in cards], [
            "Бокс №1 — Сытный", "Бокс №2 — Куриный", "Бокс №3 — Бейгл",
            "Бокс №4 — Профитроли", "Бокс №5 — Семга", "Бокс №6 — Тунец",
            "Бокс №7 — Бейгл", "Бокс №8 — Ролл",
        ])
        self.assertEqual([len(c["description"].splitlines()) - 1 for c in cards], [3, 3, 3, 3, 3, 3, 2, 3])
        for card in cards:
            self.assertEqual(card["originalPrice"], card["price"] * 2)
            self.assertEqual(card["discountPercentage"], 50)
            self.assertEqual(card["stockQuantity"], 1)
            self.assertFalse(card["needsReview"])
            self.assertEqual(card["storeName"], "Tortikipirogi")
        self.assertEqual(cards[0]["description"], "Состав:\nКруассан с семгой — 925 ₸\nЧизкейк — 700 ₸\nМуравейник — 125 ₸")
        with patch("server.CrmClient", FakeCrmClient):
            report = upload_cards(cards, dry_run=True, config_overrides={"category_name": "Кондитерские изделия"})
        self.assertEqual(report["summary"]["ok"], 8)
        payload = report["report"][0]["payload"]
        self.assertEqual(payload["description"], cards[0]["description"])
        self.assertEqual((payload["price"], payload["originalPrice"]), (1750, 3500))

    def test_missing_total_does_not_merge_next_box(self):
        cards = process("Бокс №1 — Первый\nТорт — 100 ₸\nБокс №2 — Второй\nПирог — 200 ₸\nИтого: 200 ₸")
        self.assertEqual(len(cards), 2)
        self.assertTrue(cards[0]["needsReview"])
        self.assertFalse(cards[1]["needsReview"])

    def test_invalid_box_is_reviewed(self):
        for body in ["Торт — 100 ₸\nИтого: 200 ₸", "Итого: 100 ₸", "Торт — 0 ₸\nИтого: 0 ₸", "Непонятный состав\nИтого: 100 ₸"]:
            with self.subTest(body=body):
                cards = process("Бокс №1 — Тест\n" + body)
                self.assertEqual(len(cards), 1)
                self.assertTrue(cards[0]["needsReview"])

    def test_html_spaces_dash_variants_and_mixed_single_products(self):
        cards = process("Трайфл-760\nБокс №1 – Тест 🥐\n🍰 Шок-пломбир - 1&#x20;750 ₸\n💰 Итого: 1\u202f750 ₸\nТрайфл-760")
        self.assertEqual(len(cards), 3)
        self.assertFalse(any(c["needsReview"] for c in cards))
        self.assertEqual(cards[1]["price"], 1750)
        self.assertIn("Шок-пломбир — 1750 ₸", cards[1]["description"])
        self.assertEqual(cards[2]["discountPercentage"], 20)


if __name__ == "__main__":
    unittest.main()
