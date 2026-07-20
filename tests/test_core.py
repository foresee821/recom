import unittest
from collections import Counter
from pathlib import Path

import app


class IntentParserTests(unittest.TestCase):
    def test_recommendation_can_reduce_running_shoes_and_pull_home(self):
        intent = app.parse_intent("少点跑鞋，今天想看看家居")

        self.assertEqual(intent["type"], "exclude")
        self.assertIn(("category", "neq", "跑鞋"), self._slot_values(intent))
        self.assertIn(("category", "eq", "家居"), self._slot_values(intent))

    def test_search_adds_height_and_hard_price_limit(self):
        intent = app.parse_intent("要能增高的，500元以内")

        height = next(item for item in intent["slots"] if item["value"] == "增高")
        price = next(item for item in intent["slots"] if item["name"] == "price")
        self.assertEqual(height["operator"], "eq")
        self.assertEqual(height["strength"], "hard")
        self.assertEqual(price["value"], 500)
        self.assertEqual(price["strength"], "hard")

    def test_remove_height_overrides_existing_positive_condition(self):
        existing = [app.slot("attribute", "eq", "增高", "hard", "增高")]
        intent = app.parse_intent("不要增高了")

        merged = app.merge_conditions(existing, intent)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["operator"], "neq")
        self.assertEqual(merged[0]["label"], "排除增高")

    def test_gender_correction_contains_negative_and_positive_slots(self):
        intent = app.parse_intent("不是女款，是男款")

        self.assertEqual(intent["type"], "correct")
        self.assertIn(("attribute", "neq", "女款"), self._slot_values(intent))
        self.assertIn(("attribute", "eq", "男款"), self._slot_values(intent))

    def test_explore_intent(self):
        intent = app.parse_intent("想看点没接触过的新鲜东西")

        self.assertEqual(intent["type"], "explore")
        self.assertEqual(intent["mode"], "explore")
        self.assertEqual(intent["route"]["name"], "inspiration_discovery")
        self.assertEqual(intent["slots"][0]["value"], "新鲜感")

    def test_product_intent_routes_to_constraint_ranking(self):
        intent = app.parse_intent("想看适合学生的法式裙子，300元以内")

        self.assertEqual(intent["mode"], "product")
        self.assertEqual(intent["route"]["name"], "constraint_ranking")
        self.assertIn(("category", "eq", "连衣裙"), self._slot_values(intent))
        self.assertIn(("audience", "eq", "学生"), self._slot_values(intent))
        self.assertIn(("style", "eq", "法式"), self._slot_values(intent))
        self.assertIn(("price", "lte", 300), self._slot_values(intent))

    def test_scenario_intent_expands_life_task_into_product_bundle(self):
        intent = app.parse_intent("我准备去露营")

        self.assertEqual(intent["mode"], "scenario")
        self.assertEqual(intent["route"]["name"], "scenario_bundle")
        self.assertEqual(
            intent["scenario"]["targets"],
            ["帐篷", "折叠椅", "露营灯", "驱蚊"],
        )

    def test_explore_language_wins_over_goal_phrase(self):
        intent = app.parse_intent("最近可以买点什么提升幸福感？")

        self.assertEqual(intent["mode"], "explore")
        self.assertEqual(intent["exploreTheme"], "inspiration")

    def test_explicit_product_wins_over_related_scenario_word(self):
        intent = app.parse_intent("周末露营要买帐篷")

        self.assertEqual(intent["mode"], "product")
        self.assertIn(("category", "eq", "帐篷"), self._slot_values(intent))

    def test_water_cup_expression_is_understood(self):
        intent = app.parse_intent("我想看水杯")

        self.assertEqual(intent["type"], "pull")
        self.assertIn(("category", "eq", "水杯"), self._slot_values(intent))
        self.assertEqual(intent["slots"][0]["label"], "增加水杯")

    def test_common_spoken_product_categories_are_understood(self):
        cases = {
            "想看口红": "口红",
            "换个蓝牙耳机": "耳机",
            "想买一台手机": "手机",
            "家里缺个咖啡机": "咖啡机",
            "给猫买猫粮": "猫粮",
            "周末露营要帐篷": "帐篷",
            "想买通勤包包": "箱包",
            "换个机械键盘": "键盘",
            "需要车载手机支架": "汽车用品",
            "看看夏天的连衣裙": "连衣裙",
            "买点新鲜水果": "水果",
            "想找文学小说": "图书",
            "想看看香水": "香水",
            "需要母婴用品": "宝宝用品",
            "最近想换护肤品": "护肤",
        }

        for transcript, expected in cases.items():
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                self.assertIn(("category", "eq", expected), self._slot_values(intent))

    def test_expanded_common_catalog_aliases_are_understood(self):
        cases = {
            "家里抽纸用完了": "纸巾",
            "想买个吹头发的": "吹风机",
            "推荐一个煮饭锅": "电饭煲",
            "给我看看扫地机": "扫地机器人",
            "需要一台学习平板": "平板电脑",
            "想买手提电脑": "笔记本电脑",
            "有没有便携音响": "蓝牙音箱",
            "想看看裤子": "牛仔裤",
            "买一件防晒衣": "外套",
            "给宝宝买奶粉": "奶粉",
            "新手钓鱼用什么鱼竿": "鱼竿",
        }

        for transcript, expected in cases.items():
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                self.assertIn(("category", "eq", expected), self._slot_values(intent))

    def test_multiple_positive_and_negative_categories_can_coexist(self):
        intent = app.parse_intent("不要零食，想看蓝牙耳机和水杯")
        values = self._slot_values(intent)

        self.assertEqual(intent["type"], "exclude")
        self.assertIn(("category", "neq", "零食"), values)
        self.assertIn(("category", "eq", "耳机"), values)
        self.assertIn(("category", "eq", "水杯"), values)

    def test_category_can_be_combined_with_attributes_and_price(self):
        intent = app.parse_intent("想看黑色无线耳机，500元以内")
        values = self._slot_values(intent)

        self.assertIn(("category", "eq", "耳机"), values)
        self.assertIn(("attribute", "eq", "黑色"), values)
        self.assertIn(("attribute", "eq", "无线"), values)
        self.assertIn(("price", "lte", 500), values)

    def test_explanation_phrase_is_not_supported(self):
        intent = app.parse_intent("这种为什么推给我")

        self.assertEqual(intent["type"], "unknown")
        self.assertEqual(intent["slots"], [])

    def test_unknown_expression_is_safe(self):
        intent = app.parse_intent("今天心情还行")

        self.assertEqual(intent["type"], "unknown")
        self.assertEqual(intent["slots"], [])

    @staticmethod
    def _slot_values(intent):
        return {(item["name"], item["operator"], item["value"]) for item in intent["slots"]}


class RankingTests(unittest.TestCase):
    def test_recognized_home_intent_never_returns_an_empty_feed(self):
        for transcript, expected_value in (
            ("只看OTC药品，50元以内", "OTC药品"),
            ("只看电吹风，50元以内", "吹风机"),
        ):
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                conditions = app.merge_conditions([], intent)
                ranked = app.rank_results_for_display("recommend", conditions, intent)

                self.assertTrue(ranked["fallbackApplied"])
                self.assertGreater(len(ranked["exact"]), 0)
                self.assertTrue(
                    any(
                        app.product_contains_value(app.PRODUCT_BY_ID[item_id], expected_value)
                        for item_id in ranked["exact"][:10]
                    ),
                    ranked["exact"][:10],
                )

    def test_home_intent_pushes_home_items_ahead_of_running_shoes(self):
        intent = app.parse_intent("少点跑鞋，多看看家居")
        ranked = app.rank_results("recommend", intent["slots"])["exact"]

        first_categories = [app.PRODUCT_BY_ID[item_id]["category"] for item_id in ranked[:6]]
        self.assertIn("家居", first_categories)
        self.assertNotIn("跑鞋", first_categories)

    def test_search_hard_constraints_never_enter_exact_results(self):
        intent = app.parse_intent("要增高的，500元以内")
        ranked = app.rank_results("search", intent["slots"])

        self.assertGreaterEqual(len(ranked["exact"]), 3)
        for item_id in ranked["exact"]:
            item = app.PRODUCT_BY_ID[item_id]
            self.assertIn("增高", item["attributes"])
            self.assertLessEqual(item["price"], 500)
        self.assertIn("shoe-08", ranked["near"])

    def test_impossible_hard_constraint_separates_near_matches(self):
        conditions = [app.slot("price", "lte", 50, "hard", "≤¥50")]
        ranked = app.rank_results("search", conditions)

        self.assertEqual(ranked["exact"], [])
        self.assertGreater(len(ranked["near"]), 0)

    def test_exploration_increases_novel_items(self):
        intent = app.parse_intent("想看点没接触过的新鲜东西")
        ranked = app.rank_results("recommend", intent["slots"], intent)["exact"]

        novelty_scores = [app.PRODUCT_BY_ID[item_id]["novelty"] for item_id in ranked[:6]]
        self.assertGreaterEqual(min(novelty_scores), 6)
        self.assertGreaterEqual(len({app.PRODUCT_BY_ID[item_id]["category"] for item_id in ranked[:6]}), 4)

    def test_camping_scenario_recommends_a_complete_bundle(self):
        intent = app.parse_intent("我准备去露营")
        ranked = app.rank_results("recommend", intent["slots"], intent)["exact"]
        first_items = [app.PRODUCT_BY_ID[item_id] for item_id in ranked[:4]]

        for expected in ("帐篷", "折叠椅", "露营灯", "驱蚊"):
            self.assertTrue(
                any(app.product_contains_value(item, expected) for item in first_items),
                f"missing {expected}: {[item['title'] for item in first_items]}",
            )

    def test_product_brand_origin_and_budget_constraints(self):
        intent = app.parse_intent("我想买手机，只看国产，不要苹果，3000元以内")
        ranked = app.rank_results("recommend", intent["slots"], intent)

        self.assertEqual(ranked["exact"][0], "phone-02")
        self.assertNotIn("phone-01", ranked["exact"])

    def test_new_intents_append_without_clearing_existing_session(self):
        product_intent = app.parse_intent("我想看水杯")
        session = app.merge_conditions([], product_intent)
        scenario_intent = app.parse_intent("我要养猫")
        session = app.merge_conditions(session, scenario_intent)

        self.assertIn(("category", "eq", "水杯"), {
            (item["name"], item["operator"], item["value"]) for item in session
        })
        self.assertTrue(any(item.get("sourceMode") == "scenario" for item in session))

        explore_intent = app.parse_intent("最近有什么新鲜玩意")
        session = app.merge_conditions(session, explore_intent)
        self.assertTrue(any(item.get("sourceMode") == "scenario" for item in session))
        self.assertTrue(any(item.get("sourceMode") == "explore" for item in session))

    def test_price_follow_up_inherits_existing_camping_scenario(self):
        camping = app.parse_intent("我想去露营")
        session = app.merge_conditions([], camping)
        price_follow_up = app.parse_intent("我想要500元以下的")
        session = app.merge_conditions(session, price_follow_up)
        ranked = app.rank_results("recommend", session, price_follow_up)["exact"]

        self.assertTrue(any(item.get("sourceMode") == "scenario" for item in session))
        self.assertIn(("price", "lte", 500), {
            (item["name"], item["operator"], item["value"]) for item in session
        })
        self.assertGreaterEqual(len(ranked), 4)
        self.assertTrue(all(app.PRODUCT_BY_ID[item_id]["price"] <= 500 for item_id in ranked))
        first_items = [app.PRODUCT_BY_ID[item_id] for item_id in ranked[:4]]
        for expected in ("帐篷", "折叠椅", "露营灯", "驱蚊"):
            self.assertTrue(any(app.product_contains_value(item, expected) for item in first_items))

    def test_product_follow_up_is_added_to_existing_scenario_bundle(self):
        camping = app.parse_intent("我想去露营")
        session = app.merge_conditions([], camping)
        cup_follow_up = app.parse_intent("再加一个水杯")
        session = app.merge_conditions(session, cup_follow_up)
        ranked = app.rank_results("recommend", session, cup_follow_up)["exact"]

        self.assertTrue(any(item["value"] == "水杯" for item in session))
        self.assertTrue(
            any(app.product_contains_value(app.PRODUCT_BY_ID[item_id], "水杯") for item_id in ranked[:6])
        )

    def test_water_cup_intent_pushes_cups_to_the_front(self):
        intent = app.parse_intent("想看看杯子")
        ranked = app.rank_results("recommend", intent["slots"])["exact"]

        self.assertTrue(
            all(app.product_contains_value(app.PRODUCT_BY_ID[item_id], "水杯") for item_id in ranked[:2])
        )

    def test_expanded_catalog_intents_rank_matching_products_first(self):
        cases = {
            "想看口红": "口红",
            "想看无线耳机": "耳机",
            "想买手机": "手机",
            "家用咖啡机": "咖啡机",
            "买点零食": "零食",
            "给猫买猫粮": "猫粮",
            "看看婴儿车": "婴儿车",
            "露营帐篷": "帐篷",
            "通勤包包": "箱包",
            "机械键盘": "机械键盘",
            "车载手机支架": "汽车用品",
            "换护肤品": "护肤",
            "夏季连衣裙": "连衣裙",
            "新鲜水果": "水果",
            "文学小说": "图书",
            "清新香水": "香水",
        }

        for transcript, expected_value in cases.items():
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                ranked = app.rank_results("recommend", intent["slots"])["exact"]
                self.assertTrue(
                    app.product_contains_value(app.PRODUCT_BY_ID[ranked[0]], expected_value),
                    ranked[:3],
                )

    def test_multiple_positive_categories_are_interleaved(self):
        intent = app.parse_intent("想看蓝牙耳机和水杯")
        ranked = app.rank_results("recommend", intent["slots"])["exact"]

        first_types = [
            "耳机" if app.product_contains_value(app.PRODUCT_BY_ID[item_id], "耳机") else "水杯"
            for item_id in ranked[:4]
        ]
        self.assertEqual(first_types, ["耳机", "水杯", "耳机", "水杯"])

    def test_bootstrap_has_local_complete_demo_data(self):
        payload = app.bootstrap_payload()

        self.assertGreaterEqual(len(payload["products"]), 85)
        self.assertTrue(all(item["image"].startswith("/assets/") for item in payload["products"]))
        self.assertEqual(payload["searchQuery"], "男生白色运动鞋")
        self.assertNotIn("explain", payload["examples"])
        self.assertEqual(
            [app.parse_intent(example)["mode"] for example in payload["examples"]["recommend"]],
            [
                "scenario",
                "explore",
                "scenario",
                "scenario",
                "explore",
                "product",
            ],
        )

    def test_new_voice_cases_have_at_least_ten_local_image_products(self):
        cases = [
            ("给我推荐点健身好物", "scenario", "fitcase-"),
            ("有没有让我眼前一亮的好物", "explore", "wow-"),
        ]

        for transcript, expected_mode, expected_prefix in cases:
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                ranked = app.rank_results("recommend", intent["slots"], intent)["exact"]

                self.assertEqual(intent["mode"], expected_mode)
                self.assertGreaterEqual(
                    sum(item_id.startswith(expected_prefix) for item_id in ranked[:12]),
                    10,
                    ranked[:12],
                )

    def test_dress_follow_ups_keep_category_and_add_style_and_color(self):
        session = []
        intent = app.parse_intent("给我推荐一些好看的裙子")
        session = app.merge_conditions(session, intent)
        varied_ranked = app.rank_results("recommend", session, intent)["exact"]
        self.assertGreaterEqual(
            sum(item_id.startswith("dressbase-") for item_id in varied_ranked[:12]),
            10,
            varied_ranked[:12],
        )

        intent = app.parse_intent("想要韩式风格")
        session = app.merge_conditions(session, intent)
        korean_ranked = app.rank_results("recommend", session, intent)["exact"]
        self.assertGreaterEqual(
            sum(item_id.startswith("dresskorean-") for item_id in korean_ranked[:12]),
            10,
            korean_ranked[:12],
        )

        intent = app.parse_intent("想要颜色浅一点")
        session = app.merge_conditions(session, intent)

        session_values = {
            (item["name"], item["operator"], item["value"]) for item in session
        }
        self.assertIn(("category", "eq", "连衣裙"), session_values)
        self.assertIn(("style", "eq", "韩式"), session_values)
        self.assertIn(("attribute", "eq", "浅色"), session_values)

        ranked = app.rank_results("recommend", session, intent)["exact"]
        self.assertGreaterEqual(
            sum(item_id.startswith("dresscase-") for item_id in ranked[:12]),
            10,
            ranked[:12],
        )

    def test_six_preset_cases_have_at_least_ten_local_image_products(self):
        cases = [
            ("我的出租屋还能更舒服吗？", "scenario", "rental-"),
            ("我要去看演唱会有什么推荐好物", "scenario", "concert-"),
            ("买什么东西可以提升幸福感", "explore", "happy-"),
            ("有什么好用的防晒霜", "product", "sunscreen-"),
            ("给我推荐点健身好物", "scenario", "fitcase-"),
            ("有没有让我眼前一亮的好物", "explore", "wow-"),
        ]

        for transcript, expected_mode, expected_prefix in cases:
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                ranked = app.rank_results("recommend", intent["slots"], intent)["exact"]

                self.assertEqual(intent["mode"], expected_mode)
                self.assertGreaterEqual(len(ranked), 10)
                self.assertGreaterEqual(
                    sum(item_id.startswith(expected_prefix) for item_id in ranked[:12]),
                    10,
                    ranked[:12],
                )
                self.assertTrue(
                    all(app.PRODUCT_BY_ID[item_id]["image"].startswith("/assets/") for item_id in ranked[:10])
                )

        for filename in (
            "case-rental-products-v1.png",
            "case-concert-products-v1.png",
            "case-happiness-products-v1.png",
            "case-sunscreen-products-v1.png",
            "case-diverse-dresses-v1.png",
            "case-korean-dark-dresses-v1.png",
            "case-korean-dresses-v1.png",
            "case-fitness-products-v1.png",
            "case-eye-catching-products-v1.png",
        ):
            self.assertTrue((app.STATIC_DIR / "assets" / filename).is_file(), filename)

    def test_every_catalog_intent_has_matching_products(self):
        for value, display, _ in app.COMMODITY_INTENTS:
            with self.subTest(intent=display):
                condition = app.slot("category", "eq", value, "soft", display)
                matches = [item for item in app.PRODUCTS if app.product_matches(item, condition)]
                self.assertGreater(len(matches), 0)

    def test_common_catalog_has_two_products_and_local_sprite_for_each_group(self):
        self.assertGreaterEqual(len(app.PRODUCTS), 246)
        for group, (_, intent_value, _) in app.COMMON_CATALOG_GROUPS.items():
            with self.subTest(group=group):
                matching_ids = [
                    item["id"]
                    for item in app.PRODUCTS
                    if item["id"].startswith(f"common-{group}-")
                    and app.product_contains_value(item, intent_value)
                ]
                self.assertEqual(len(matching_ids), 2)

        asset = app.STATIC_DIR / "assets" / "common-products-v1.png"
        self.assertTrue(asset.is_file())
        self.assertGreater(asset.stat().st_size, 100_000)

    def test_specific_common_product_stays_ahead_of_context_and_audience_words(self):
        cases = {
            "家里抽纸用完了": "纸巾",
            "给宝宝买奶粉": "奶粉",
            "新手钓鱼用什么鱼竿": "鱼竿",
        }

        for transcript, expected_value in cases.items():
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                ranked = app.rank_results("recommend", intent["slots"], intent)["exact"][:2]
                self.assertTrue(
                    all(
                        app.product_contains_value(app.PRODUCT_BY_ID[item_id], expected_value)
                        for item_id in ranked
                    ),
                    ranked,
                )


class TaxonomyCatalogTests(unittest.TestCase):
    def test_excel_taxonomy_generates_ten_products_per_category_pair(self):
        counts = Counter(
            (item["xcat1"], item["xcat2"])
            for item in app.TAXONOMY_PRODUCTS
        )

        self.assertEqual(len(app.TAXONOMY_PARENT_NAMES), 148)
        self.assertEqual(len(app.TAXONOMY_CATEGORIES), 1341)
        self.assertEqual(len(app.TAXONOMY_PRODUCTS), 13410)
        self.assertEqual(len(counts), 1341)
        self.assertEqual(set(counts.values()), {10})

    def test_spoken_product_maps_to_excel_primary_and_secondary_categories(self):
        cases = {
            "想买个吹风机": ("个人护理", "电吹风"),
            "我想买水杯": ("厨房餐饮具", "杯子/水杯/水壶"),
            "给我推荐连衣裙": ("女装", "连衣裙"),
            "想买电饭煲": ("中式厨房", "电饭煲"),
        }

        for transcript, expected in cases.items():
            with self.subTest(transcript=transcript):
                intent = app.parse_intent(transcript)
                self.assertEqual(
                    (intent["taxonomy"]["xcat1"], intent["taxonomy"]["xcat2"]),
                    expected,
                )

    def test_ambiguous_secondary_uses_spoken_primary_category(self):
        intent = app.parse_intent("厨房餐饮具里的餐具")

        self.assertEqual(intent["taxonomy"]["xcat1"], "厨房餐饮具")
        self.assertEqual(intent["taxonomy"]["xcat2"], "餐具")

    def test_primary_category_only_returns_diverse_secondary_categories(self):
        intent = app.parse_intent("看看个人护理")
        ranked = app.rank_results("recommend", intent["slots"], intent)["exact"][:10]
        items = [app.PRODUCT_BY_ID[item_id] for item_id in ranked]

        self.assertEqual(intent["taxonomy"], {"xcat1": "个人护理", "xcat2": None})
        self.assertTrue(all(item["xcat1"] == "个人护理" for item in items))
        self.assertGreaterEqual(len({item["xcat2"] for item in items}), 8)

    def test_secondary_category_returns_its_ten_concrete_products(self):
        intent = app.parse_intent("想买个吹风机")
        ranked = app.rank_results("recommend", intent["slots"], intent)["exact"]
        items = [app.PRODUCT_BY_ID[item_id] for item_id in ranked]

        self.assertEqual(len(items), 10)
        self.assertTrue(all(item["xcat1"] == "个人护理" for item in items))
        self.assertTrue(all(item["xcat2"] == "电吹风" for item in items))

    def test_price_follow_up_keeps_taxonomy_category(self):
        category_intent = app.parse_intent("想买电饭煲")
        session = app.merge_conditions([], category_intent)
        price_intent = app.parse_intent("500元以内")
        session = app.merge_conditions(session, price_intent)
        ranked = app.rank_results("recommend", session, price_intent)["exact"]
        items = [app.PRODUCT_BY_ID[item_id] for item_id in ranked]

        self.assertGreater(len(items), 0)
        self.assertTrue(all(item["xcat2"] == "电饭煲" for item in items))
        self.assertTrue(all(item["price"] <= 500 for item in items))

    def test_api_can_return_dynamic_products_without_bloating_bootstrap(self):
        intent = app.parse_intent("给我推荐连衣裙")
        ranked = app.rank_results("recommend", intent["slots"], intent)
        dynamic_products = app.products_for_ranked_results(ranked)
        bootstrap_ids = {item["id"] for item in app.bootstrap_payload()["products"]}

        self.assertEqual(len(dynamic_products), 10)
        self.assertTrue(all(item["id"].startswith("tax-") for item in dynamic_products))
        self.assertTrue(all(item["id"] not in bootstrap_ids for item in dynamic_products))


class VoiceInteractionSourceTests(unittest.TestCase):
    def test_home_feed_has_a_defensive_non_empty_result_fallback(self):
        source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function usableResultIds", source)
        self.assertIn("state.previous?.recommendationIds", source)
        self.assertIn("state.bootstrap.initialRecommendations", source)

    def test_mobile_voice_does_not_preflight_or_surface_aborted_message(self):
        source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("getUserMedia", source)
        self.assertNotIn("语音识别已取消", source)
        self.assertIn("recognition.onstart", source)
        self.assertIn("刚刚没有录到声音，请重新按住说话", source)

    def test_voice_fallback_never_simulates_a_recognition_result(self):
        source = (Path(__file__).parents[1] / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("window.SpeechRecognition || window.webkitSpeechRecognition", source)
        self.assertIn("请使用 Chrome、Edge 或 Safari", source)
        self.assertNotIn("演示识别", source)
        self.assertNotIn("runDemoVoice", source)
        self.assertNotIn("demoVoiceMode", source)
        self.assertNotIn("bootstrap.examples[state.scene][0]", source)

    def test_static_assets_work_under_a_github_pages_subpath(self):
        static_dir = Path(__file__).parents[1] / "static"
        source = "\n".join(
            (static_dir / filename).read_text(encoding="utf-8")
            for filename in ("index.html", "styles.css", "app.js")
        )

        self.assertNotIn('src="/assets/', source)
        self.assertNotIn('href="/styles.css', source)
        self.assertNotIn('src="/app.js', source)
        self.assertNotIn("url('/assets/", source)


if __name__ == "__main__":
    unittest.main()
