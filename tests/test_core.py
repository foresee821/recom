import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["INTENT_ENGINE"] = "rules"

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


class CategorySelectorTests(unittest.TestCase):
    def test_candidates_contain_only_real_catalog_categories(self):
        candidates = app.category_selection_candidates("想看蓝牙耳机，500元以内")
        valid_xcat1 = set(app.TAXONOMY_PARENT_NAMES)
        valid_xcat2 = {item["xcat2"] for item in app.TAXONOMY_CATEGORIES}

        self.assertEqual(candidates[0]["name"], "无线耳机")
        self.assertTrue(all(
            item["name"] in (valid_xcat2 if item["level"] == "xcat2" else valid_xcat1)
            for item in candidates
        ))

    def test_prompt_only_allows_one_existing_candidate_id(self):
        candidates = app.category_selection_candidates("我想看留学的东西")
        prompt = app.intent_system_prompt(candidates)

        self.assertIn("最直接有帮助的 1 个", prompt)
        self.assertIn("只能返回一个候选编号", prompt)
        self.assertIn('{"category_id":"编号"}', prompt)
        self.assertNotIn('"mode":"product|scenario|explore|unknown"', prompt)

    def test_low_category_scores_trigger_hidden_fallback_instead_of_visible_selection(self):
        candidates = app.category_selection_candidates("今天随便看看")
        low_scores = {group_id: 1 for group_id, _, _ in app.CATEGORY_GROUPS}

        with patch.object(app, "call_category_selector", return_value=low_scores) as selector:
            selected = app.select_category_ids_with_api(
                "今天随便看看",
                candidates,
                api_key="test-key",
                model="test-model",
                timeout=20,
                base_url="",
            )

        self.assertEqual(selected, [])
        self.assertEqual(selector.call_count, 1)

    def test_model_output_is_resolved_by_id_and_generated_names_are_ignored(self):
        candidates = [
            {"id": "c001", "level": "xcat2", "name": "无线耳机", "parent": "影音电器"},
            {"id": "c002", "level": "xcat1", "name": "居家日用", "parent": ""},
        ]
        intent = app.normalize_api_intent({
            "include_ids": ["c001", "不存在的类目", "c999"],
            "exclude_ids": [],
            "price_lte": "500元",
        }, "想看蓝牙耳机，500元以内", candidates)

        slots = {(item["name"], item["operator"], item["value"]) for item in intent["slots"]}
        self.assertEqual(intent["selectedCategories"], ["无线耳机"])
        self.assertIn(("xcat2", "eq", "无线耳机"), slots)
        self.assertIn(("price", "lte", 500), slots)
        self.assertFalse(any(value == "不存在的类目" for _, _, value in slots))

    def test_exclude_only_does_not_trigger_random_fallback(self):
        candidates = [
            {"id": "c001", "level": "xcat1", "name": "美容护肤/美体/精油", "parent": ""},
        ]
        intent = app.normalize_api_intent({
            "include_ids": [],
            "exclude_ids": ["c001"],
        }, "不要看护肤了", candidates)

        self.assertFalse(intent["selectionFallback"])
        self.assertEqual(intent["selectedCategories"], [])
        self.assertEqual(intent["excludedCategories"], ["美容护肤/美体/精油"])
        self.assertEqual(
            [(item["name"], item["operator"], item["value"]) for item in intent["slots"]],
            [("xcat1", "neq", "美容护肤/美体/精油")],
        )

    def test_api_maps_mixed_add_and_remove_to_real_categories(self):
        def fake_select(query, candidates, **_kwargs):
            target = (
                "美容护肤/美体/精油"
                if query == "护肤"
                else "女装/女士精品"
            )
            return [next(item["id"] for item in candidates if item["name"] == target)]

        with patch.object(app, "select_category_ids_with_api", side_effect=fake_select):
            with patch.dict(os.environ, {
                "INTENT_API_KEY": "test-key",
                "INTENT_API_MODEL": "test-model",
            }):
                intent = app.parse_intent_with_api("现在不要看护肤了，看看穿搭")

        slots = {(item["name"], item["operator"], item["value"]) for item in intent["slots"]}
        self.assertEqual(intent["polarity"], "mixed")
        self.assertIn(("xcat1", "neq", "美容护肤/美体/精油"), slots)
        self.assertIn(("xcat1", "eq", "女装/女士精品"), slots)
        self.assertEqual(
            app.feedback_for(intent),
            "已减少美容护肤/美体/精油，增加女装/女士精品、男装",
        )

    def test_empty_model_selection_randomly_samples_real_categories_without_rejection_copy(self):
        candidates = app.category_selection_candidates("随便看看")
        pool = [item for item in candidates if item["level"] == "xcat1"]
        sampled = [pool[2], pool[-3]]
        fake_random = SimpleNamespace(
            randint=lambda start, end: 2,
            sample=lambda population, count: sampled[:count],
        )

        with patch("app.random.SystemRandom", return_value=fake_random):
            intent = app.normalize_api_intent({}, "随便看看", candidates)

        self.assertEqual(intent["type"], "pull")
        self.assertTrue(intent["selectionFallback"])
        self.assertEqual(intent["selectedCategories"], [item["name"] for item in sampled])
        self.assertTrue(all(item.get("hidden") for item in intent["slots"]))
        feedback = app.feedback_for(intent)
        self.assertEqual(feedback, "先为你推荐这些")
        self.assertNotIn("随机", feedback)
        self.assertFalse(any(item["name"] in feedback for item in sampled))
        self.assertNotIn("没听懂", feedback)
        self.assertNotIn("没识别", feedback)

    def test_conversation_conditions_accumulate_until_explicit_reset(self):
        existing = [
            app.slot("xcat1", "eq", "女装/女士精品", "soft", "女装/女士精品"),
            app.slot("price", "lte", 800, "hard", "≤¥800"),
        ]
        incoming = {
            "slots": [
                app.slot("xcat1", "eq", "影音电器", "soft", "影音电器"),
                app.slot("price", "gte", 200, "hard", "≥¥200"),
            ],
        }

        merged = app.merge_conditions(existing, incoming)
        values = {(item["name"], item["operator"], item["value"]) for item in merged}
        self.assertEqual(len(merged), 4)
        self.assertIn(("xcat1", "eq", "女装/女士精品"), values)
        self.assertIn(("xcat1", "eq", "影音电器"), values)
        self.assertIn(("price", "lte", 800), values)
        self.assertIn(("price", "gte", 200), values)

    def test_random_fallback_conditions_are_replaced_not_accumulated(self):
        existing = [
            app.slot("price", "lte", 800, "hard", "≤¥800"),
            {**app.slot("xcat1", "eq", "旧随机类目", "soft", "旧随机类目"), "hidden": True},
        ]
        incoming = {
            "slots": [
                {**app.slot("xcat1", "eq", "新随机类目", "soft", "新随机类目"), "hidden": True},
            ],
        }

        merged = app.merge_conditions(existing, incoming)
        self.assertEqual(
            [(item["name"], item["value"], item.get("hidden", False)) for item in merged],
            [("price", 800, False), ("xcat1", "新随机类目", True)],
        )
        self.assertEqual(
            app.visible_session_conditions(merged),
            [app.slot("price", "lte", 800, "hard", "≤¥800")],
        )

    def test_negative_category_retracts_related_positive_condition(self):
        existing = [
            app.slot("xcat1", "eq", "美容护肤/美体/精油", "soft", "美容护肤/美体/精油"),
            app.slot("price", "lte", 800, "hard", "≤¥800"),
        ]
        incoming = {
            "slots": [
                app.slot("xcat2", "neq", "面部护理套装", "soft", "排除面部护理套装"),
                app.slot("xcat1", "eq", "女装/女士精品", "soft", "女装/女士精品"),
            ],
        }

        merged = app.merge_conditions(existing, incoming)
        values = {(item["name"], item["operator"], item["value"]) for item in merged}
        self.assertNotIn(("xcat1", "eq", "美容护肤/美体/精油"), values)
        self.assertIn(("xcat2", "neq", "面部护理套装"), values)
        self.assertIn(("xcat1", "eq", "女装/女士精品"), values)
        self.assertIn(("price", "lte", 800), values)

    def test_multiple_selected_categories_use_or_semantics_and_are_interleaved(self):
        conditions = [
            app.slot("xcat1", "eq", "女装/女士精品", "soft", "女装/女士精品"),
            app.slot("xcat1", "eq", "影音电器", "soft", "影音电器"),
        ]
        ranked = app.rank_results_for_display("recommend", conditions)["exact"][:12]
        parents = [app.PRODUCT_BY_ID[item_id]["xcat1"] for item_id in ranked]

        self.assertGreaterEqual(len(ranked), 10)
        self.assertTrue(set(parents).issubset({"女装/女士精品", "影音电器"}))
        self.assertEqual(parents[:4], ["女装/女士精品", "影音电器"] * 2)

    def test_whale_sdk_uses_short_non_streaming_response(self):
        class FakeTextGeneration:
            request = None

            @classmethod
            def set_api_key(cls, key, **kwargs):
                return None

            @classmethod
            def chat(cls, **kwargs):
                cls.request = kwargs
                return "response"

        with patch.dict(sys.modules, {"whale": SimpleNamespace(TextGeneration=FakeTextGeneration)}):
            with patch.object(app, "_WHALE_CONFIG_SIGNATURE", None):
                app.call_whale_chat(
                    api_key="test-secret",
                    model="intent-model",
                    messages=[{"role": "user", "content": "测试"}],
                    timeout=20,
                    base_url=None,
                )

        self.assertFalse(FakeTextGeneration.request["stream"])
        self.assertEqual(FakeTextGeneration.request["temperature"], 0)
        self.assertEqual(FakeTextGeneration.request["max_tokens"], 160)


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
        self.assertGreaterEqual(len(payload["searchWatermarks"]), 4)
        self.assertEqual(len(payload["searchWatermarks"]), len(set(payload["searchWatermarks"])))

    def test_frontend_rotates_dynamic_search_watermarks(self):
        source = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function searchWatermarkCandidates()", source)
        self.assertIn("setInterval(() => renderNextSearchWatermark(), 3000)", source)
        self.assertIn("!condition.hidden && condition.operator === \"eq\"", source)
        self.assertIn("state.lastSelectionFallback ? [] : state.recommendationIds", source)

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
