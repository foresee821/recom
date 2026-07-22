import json
import unittest
from pathlib import Path

import app


ROOT = Path(__file__).resolve().parents[1]


class IntentParserTests(unittest.TestCase):
    def test_secondary_categories_are_recognized_from_real_catalog(self):
        for transcript, expected in (("我想看项链", "项链"), ("我想看连衣裙", "连衣裙")):
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                self.assertIn(
                    ("xcat2", expected),
                    {(slot["name"], slot["value"]) for slot in intent["slots"]},
                )

    def test_unknown_expression_is_safe(self):
        intent = app.parse_intent("今天心情还行")
        self.assertEqual(intent["type"], "unknown")
        self.assertEqual(intent["slots"], [])

    def test_price_can_be_combined_with_a_real_category(self):
        intent = app.parse_intent("我想看500元以内的连衣裙")
        slots = {(item["name"], item["operator"], item["value"]) for item in intent["slots"]}
        self.assertIn(("xcat2", "eq", "连衣裙"), slots)
        self.assertIn(("price", "lte", 500), slots)


class RealCatalogTests(unittest.TestCase):
    def test_real_catalog_replaces_legacy_and_template_products(self):
        self.assertEqual(len(app.TAXONOMY_PRODUCTS), 22679)
        self.assertEqual(app.PRODUCTS, [])
        self.assertTrue(all(item["id"].startswith("catalog-") for item in app.TAXONOMY_PRODUCTS))
        self.assertFalse(any(item["id"].startswith("tax-") for item in app.PRODUCT_BY_ID.values()))
        self.assertFalse(any("测试商品请不要拍" in item["title"] for item in app.TAXONOMY_PRODUCTS))

    def test_bootstrap_does_not_send_the_full_catalog(self):
        payload = app.bootstrap_payload()
        self.assertEqual(payload["products"], [])
        self.assertEqual(payload["initialRecommendations"], [])

    def test_secondary_category_returns_real_ranked_products(self):
        for transcript, expected in (("我想看项链", "项链"), ("我想看连衣裙", "连衣裙")):
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                conditions = app.merge_conditions([], intent)
                ranked = app.rank_results_for_display("recommend", conditions, intent)
                self.assertGreaterEqual(len(ranked["exact"]), 10)
                products = [app.PRODUCT_BY_ID[item_id] for item_id in ranked["exact"]]
                self.assertTrue(all(item["xcat2"] == expected for item in products))
                self.assertTrue(all(item["image"].startswith("https://img.alicdn.com/imgextra/") for item in products))

    def test_catalog_index_and_shards_cover_every_product(self):
        index_path = ROOT / "static" / "data" / "intent-catalog" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["productCount"], 22679)
        self.assertEqual(index["xcat1Count"], 103)
        self.assertEqual(index["xcat2Count"], 1456)
        self.assertRegex(index["version"], r"flat_items_filtered\.csv-[0-9a-f]{12}")
        shard_dir = index_path.parent / "shards"
        shard_total = 0
        for shard in {item["shard"] for item in index["categories"]}:
            payload = json.loads((shard_dir / shard).read_text(encoding="utf-8"))
            shard_total += len(payload["products"])
        self.assertEqual(shard_total, index["productCount"])

    def test_camping_catalog_is_derived_from_the_new_catalog(self):
        payload = json.loads(
            (ROOT / "static" / "data" / "intent-products" / "camping.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["triggers"], ["露营", "野营", "野炊"])
        self.assertGreaterEqual(len(payload["products"]), 20)
        self.assertTrue(all(item["id"].startswith("catalog-") for item in payload["products"]))

    def test_homepage_catalog_remains_independent(self):
        home = json.loads((ROOT / "static" / "data" / "home-products.json").read_text(encoding="utf-8"))
        intent_ids = set(app.PRODUCT_BY_ID)
        self.assertEqual(len(home["products"]), 1348)
        self.assertFalse(intent_ids.intersection(item["id"] for item in home["products"]))
        self.assertFalse(any("测试商品请不要拍" in item["title"] for item in home["products"]))

    def test_frontend_loads_catalog_by_category_shard(self):
        source = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('data/intent-catalog/index.json', source)
        self.assertIn('data/intent-catalog/shards/${shard}', source)
        self.assertIn("categoryCatalogProducts(transcript", source)
        self.assertIn('includes("测试商品请不要拍")', source)
        self.assertIn("categoryMatchScore(transcript", source)
        self.assertIn("interleaveCategoryProducts(groups)", source)
        self.assertIn('"吊坠": ["项坠/吊坠", "项链"]', source)


if __name__ == "__main__":
    unittest.main()
