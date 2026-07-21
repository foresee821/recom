from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT / "data" / "category_taxonomy.json"
OUTPUT_PATH = ROOT / "data" / "category_products.json"

TITLE_SUFFIXES = (
    "热销基础款",
    "高性价比精选",
    "轻量便携款",
    "耐用升级款",
    "简约实用款",
    "人气推荐款",
    "品质进阶款",
    "家庭适用款",
    "新款优选",
    "口碑畅销款",
)
FEATURES = (
    "热销",
    "高性价比",
    "轻量",
    "耐用",
    "简约",
    "人气",
    "品质",
    "实用",
    "新款",
    "口碑",
)
PRICE_POINTS = (29, 39, 59, 79, 99, 129, 199, 299, 499, 799, 1299, 1999)


def stable_digest(xcat1: str, xcat2: str) -> str:
    return hashlib.sha1(f"{xcat1}\0{xcat2}".encode("utf-8")).hexdigest()[:12]


def build_product(xcat1: str, xcat2: str, index: int) -> dict[str, Any]:
    digest = stable_digest(xcat1, xcat2)
    seed = int(digest[:8], 16)
    price = PRICE_POINTS[(seed + index * 3) % len(PRICE_POINTS)]
    feature = FEATURES[index - 1]
    secondary_aliases = [
        part.strip()
        for part in re.split(r"[/／、|（）()]", xcat2)
        if len(part.strip()) >= 2
    ]
    return {
        "id": f"tax-{digest}-{index:02d}",
        "title": f"{xcat2} {TITLE_SUFFIXES[index - 1]}",
        "category": xcat1,
        "xcat1": xcat1,
        "xcat2": xcat2,
        "price": price,
        "image": "/assets/fresh.svg",
        "attributes": list(dict.fromkeys([xcat1, xcat2, *secondary_aliases, feature])),
        "baseScore": 76 - index,
        "sales": f"{max(1, 11 - index)}万+人付款",
        "novelty": index % 6,
        "brand": "精选品牌",
        "origin": "国产",
        "audiences": [],
        "styles": [],
        "goals": [],
        "trend": 8 if index in (1, 2, 9) else 6,
    }


def build_catalog() -> dict[str, Any]:
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    products = [
        build_product(category["xcat1"], category["xcat2"], index)
        for category in taxonomy["categories"]
        for index in range(1, 11)
    ]
    return {
        "source": taxonomy["source"],
        "productsPerXcat2": 10,
        "categoryPairCount": len(taxonomy["categories"]),
        "productCount": len(products),
        "products": products,
    }


def main() -> None:
    catalog = build_catalog()
    OUTPUT_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        f"generated {catalog['productCount']} products "
        f"for {catalog['categoryPairCount']} category pairs"
    )


if __name__ == "__main__":
    main()
