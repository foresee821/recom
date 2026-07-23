from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMAGE_PREFIX = "https://img.alicdn.com/imgextra/"


def text(value: Any) -> str:
    return str(value or "").strip().replace("\\N", "")


def number(value: Any) -> float:
    try:
        return float(text(value).replace(",", ""))
    except ValueError:
        return 0


def slug(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def product_from_row(row: dict[str, str]) -> dict[str, Any] | None:
    item_id = text(row.get("item_id"))
    title = text(row.get("title"))
    xcat1 = text(row.get("cate_level1_name"))
    xcat2 = text(row.get("cate_level2_name"))
    pict_url = re.sub(
        r"^https?://img\.alicdn\.com/imgextra/", "", text(row.get("pict_url"))
    ).lstrip("/")
    if not all((item_id, title, xcat1, xcat2, pict_url)) or "测试商品请不要拍" in title:
        return None
    commodity = text(row.get("commodity_name"))
    cate_name = text(row.get("cate_name")) or xcat2
    ordercost = number(row.get("ordercost"))
    return {
        "id": f"catalog-{item_id}",
        "title": title,
        "category": cate_name,
        "xcat1": xcat1,
        "xcat2": xcat2,
        "price": number(row.get("reserve_price")),
        "image": f"{IMAGE_PREFIX}{pict_url}",
        "ordercost": ordercost,
        "sales": f"{ordercost:,.0f}人收藏",
        "attributes": list(dict.fromkeys(filter(None, (xcat1, xcat2, commodity, cate_name)))),
        "baseScore": ordercost,
        "novelty": 0,
        "brand": "淘宝",
        "origin": "",
        "audiences": [],
        "styles": [],
        "goals": [],
        "trend": 0,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the real intent catalog from CSV")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    source_digest = hashlib.sha256(args.source.read_bytes()).hexdigest()[:12]
    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "cate_level1_name", "cate_level2_name", "item_id", "title",
            "ordercost", "reserve_price", "pict_url",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        products = [product for row in reader if (product := product_from_row(row))]

    products.sort(key=lambda item: (-item["ordercost"], item["id"]))
    by_xcat1: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for product in products:
        by_xcat1[product["xcat1"]].append(product)

    shard_dir = ROOT / "static" / "data" / "intent-catalog" / "shards"
    if shard_dir.exists():
        shutil.rmtree(shard_dir)
    categories = []
    for xcat1, items in sorted(by_xcat1.items()):
        shard = f"{slug(xcat1)}.json"
        write_json(shard_dir / shard, {"xcat1": xcat1, "products": items})
        xcat2_counts: dict[str, int] = defaultdict(int)
        for item in items:
            xcat2_counts[item["xcat2"]] += 1
        categories.extend(
            {"xcat1": xcat1, "xcat2": xcat2, "shard": shard, "count": count}
            for xcat2, count in sorted(xcat2_counts.items())
        )

    source_label = args.source.name
    taxonomy = {
        "source": source_label,
        "fields": {"xcat1": "cate_level1_name", "xcat2": "cate_level2_name"},
        "categories": [{"xcat1": item["xcat1"], "xcat2": item["xcat2"]} for item in categories],
    }
    catalog = {
        "source": source_label,
        "categoryPairCount": len(categories),
        "productCount": len(products),
        "products": products,
    }
    index = {
        "version": f"{source_label}-{source_digest}",
        "productCount": len(products),
        "xcat1Count": len(by_xcat1),
        "xcat2Count": len(categories),
        "categories": categories,
    }
    write_json(ROOT / "data" / "category_taxonomy.json", taxonomy)
    write_json(ROOT / "data" / "category_products.json", catalog)
    write_json(ROOT / "static" / "data" / "intent-catalog" / "index.json", index)

    camping_terms = ("露营", "野营", "野炊", "帐篷")
    camping = [
        item for item in products
        if any(term in " ".join((item["title"], item["xcat1"], item["xcat2"], *item["attributes"])) for term in camping_terms)
    ][:120]
    for item in camping:
        item["attributes"] = list(dict.fromkeys(["露营", *item["attributes"]]))
        item["goals"] = ["露营"]
    write_json(
        ROOT / "static" / "data" / "intent-products" / "camping-new.json",
        {"scene": "camping", "triggers": ["露营", "野营", "野炊"], "products": camping},
    )
    print(
        f"Imported {len(products)} products, {len(by_xcat1)} xcat1 categories, "
        f"{len(categories)} xcat2 pairs and {len(camping)} camping products."
    )


if __name__ == "__main__":
    main()
