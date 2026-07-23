from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "category_products.json"
TARGET = ROOT / "static" / "data" / "example-products.json"
INTENT_PRODUCTS = ROOT / "static" / "data" / "intent-products"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def select_pairs(
    products: list[dict[str, Any]],
    pairs: list[tuple[str, str]],
    *,
    per_pair: int,
) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    for xcat1, xcat2 in pairs:
        matches = [
            item
            for item in products
            if item.get("xcat1") == xcat1
            and item.get("xcat2") == xcat2
            and str(item.get("image", "")).startswith("https://img.alicdn.com/")
            and "测试商品请不要拍" not in str(item.get("title", ""))
        ]
        matches.sort(key=lambda item: float(item.get("ordercost", 0)), reverse=True)
        groups.append(matches[:per_pair])

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position in range(per_pair):
        for group in groups:
            if position >= len(group):
                continue
            item = group[position]
            key = str(item.get("image") or item.get("id"))
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)
    return selected


def main() -> None:
    source_products = load_json(SOURCE)["products"]
    freshness = load_json(INTENT_PRODUCTS / "freshness.json")["products"]
    hobbies = load_json(INTENT_PRODUCTS / "trending-hobbies.json")["products"]

    examples = [
        {
            "key": "style-refresh",
            "prompt": "最近想换换穿衣风格。",
            "pattern": r"换(?:换|个|一种)?.{0,4}(?:穿衣|穿搭|服装)?风格|(?:穿衣|穿搭|服装).{0,4}换.{0,3}风格",
            "feedback": "为你换一组不同风格的穿搭",
            "bubbles": ["+ 穿衣风格", "+ 多风格"],
            "products": select_pairs(
                source_products,
                [
                    ("女装/女士精品", "连衣裙"),
                    ("女装/女士精品", "衬衫"),
                    ("女装/女士精品", "牛仔裤"),
                    ("女装/女士精品", "短外套"),
                    ("男装", "T恤"),
                    ("男装", "夹克"),
                    ("男装", "休闲裤"),
                    ("男装", "Polo衫"),
                ],
                per_pair=2,
            ),
        },
        {
            "key": "summer-wear",
            "prompt": "有没有适合夏天穿的？",
            "pattern": r"适合.{0,3}(?:夏天|夏季)穿|(?:夏天|夏季).{0,4}(?:穿|穿搭|衣服)|夏装",
            "feedback": "为你准备清爽实穿的夏季穿搭",
            "bubbles": ["+ 夏季穿搭", "+ 清爽防晒"],
            "products": select_pairs(
                source_products,
                [
                    ("女装/女士精品", "T恤"),
                    ("女装/女士精品", "时尚防晒服"),
                    ("女装/女士精品", "背心吊带"),
                    ("女装/女士精品", "连衣裙"),
                    ("男装", "T恤"),
                    ("男装", "时尚防晒服"),
                    ("男装", "背心"),
                    ("男装", "短裤"),
                ],
                per_pair=2,
            ),
        },
        {
            "key": "fresh-discovery",
            "prompt": "今天想看点不一样的。",
            "pattern": r"看点不一样|来点不一样|想看.{0,3}不一样|换点不一样",
            "feedback": "为你挑了一组跨品类的新鲜好物",
            "bubbles": ["+ 新鲜感", "+ 跨品类"],
            "products": freshness,
        },
        {
            "key": "weekend-play",
            "prompt": "有没有适合周末的新玩法？",
            "pattern": r"周末.{0,6}新玩法|新玩法.{0,6}周末|周末.{0,5}(?:玩什么|做什么)",
            "feedback": "为你找到一些周末可以尝试的新玩法",
            "bubbles": ["+ 周末玩法", "+ 新兴趣"],
            "products": hobbies,
        },
        {
            "key": "fitness-start",
            "prompt": "最近想开始健身。",
            "pattern": r"开始健身|想开始.{0,3}健身|准备健身|健身入门",
            "feedback": "为你配好一组健身入门装备",
            "bubbles": ["+ 健身入门", "+ 训练装备"],
            "products": select_pairs(
                source_products,
                [
                    ("运动/瑜伽/健身/球迷用品", "瑜伽"),
                    ("运动/瑜伽/健身/球迷用品", "踏步机/中小型健身器材"),
                    ("运动/瑜伽/健身/球迷用品", "甩脂机/小肌肉群运动器械"),
                    ("运动/瑜伽/健身/球迷用品", "运动护具"),
                    ("运动服/休闲服装", "健身服装"),
                    ("运动鞋new", "综合训练鞋/室内健身鞋"),
                ],
                per_pair=3,
            ),
        },
        {
            "key": "italy-trip",
            "prompt": "下个月去意大利，有什么需要准备的吗？",
            "pattern": r"意大利|欧洲.{0,4}(?:旅行|旅游|出行)|去欧洲",
            "feedback": "为你整理了意大利出行前需要准备的好物",
            "bubbles": ["+ 意大利旅行", "+ 出行准备"],
            "products": select_pairs(
                source_products,
                [
                    ("户外/登山/野营/旅行用品", "旅行便携装备"),
                    ("收纳整理", "旅行收纳用具"),
                    ("箱包皮具/热销女包/男包", "旅行箱"),
                    ("智能设备", "智能翻译机"),
                    ("3C数码配件", "便携电源"),
                    ("美容护肤/美体/精油", "旅行装/体验装"),
                ],
                per_pair=3,
            ),
        },
    ]

    for example in examples:
        if len(example["products"]) < 10:
            raise RuntimeError(f"{example['key']} only selected {len(example['products'])} products")

    TARGET.write_text(
        json.dumps({"version": "example-guides-v1", "examples": examples}, ensure_ascii=False),
        encoding="utf-8",
    )
    print("built", {example["key"]: len(example["products"]) for example in examples})


if __name__ == "__main__":
    main()
