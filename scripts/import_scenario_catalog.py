#!/usr/bin/env python3
"""Convert the four demo-scenario workbooks into the web catalog format."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS}

PRESET_SHEETS = [
    (
        "情境一.xlsx",
        "Q1",
        "scenario-1-q1",
        "情境一",
        "今天先别推护肤了，想看看穿搭。",
    ),
    (
        "情境一.xlsx",
        "Q2",
        "scenario-1-q2",
        "情境一",
        "想看看通勤能穿的，别太正式，也别太普通。",
    ),
    (
        "情境一.xlsx",
        "Q3",
        "scenario-1-q3",
        "情境一",
        "这些感觉不错，就是感觉有些贵，多来一点性价比高的。",
    ),
    (
        "情景二.xlsx",
        "Sheet1",
        "scenario-2-q1",
        "情景二",
        "这些最近看得有点腻了，换点新鲜的给我看看。",
    ),
    (
        "情景二.xlsx",
        "Sheet2",
        "scenario-2-q2",
        "情景二",
        "最近有没有什么新流行的兴趣爱好值得尝试？",
    ),
    (
        "情景三.xlsx",
        "1",
        "scenario-3-q1",
        "情景三",
        "我刚搬了新家，想慢慢把家布置起来",
    ),
    (
        "情景四.xlsx",
        "Sheet1",
        "scenario-4-q1",
        "情景四",
        "下周末要去见喜欢的人了",
    ),
]


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference)
    if not letters:
        return 0
    result = 0
    for character in letters.group():
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def number(value: str, default: float = 0.0) -> float:
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return default


def image_url(value: str) -> str:
    value = str(value or "").strip()
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("//"):
        return f"https:{value}"
    return f"https://img.alicdn.com/imgextra/{value.lstrip('/')}"


def workbook_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append(
                    "".join(
                        node.text or ""
                        for node in item.iter(f"{{{MAIN_NS}}}t")
                    )
                )

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationship_targets = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships
        }
        result: dict[str, list[dict[str, str]]] = {}
        for sheet in workbook.find("m:sheets", NS) or []:
            sheet_name = sheet.attrib["name"]
            relationship_id = sheet.attrib[f"{{{REL_NS}}}id"]
            target = relationship_targets[relationship_id].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            root = ET.fromstring(archive.read(target))
            rows: list[list[str]] = []
            for row in root.findall(".//m:sheetData/m:row", NS):
                values: list[str] = []
                for cell in row.findall("m:c", NS):
                    index = column_index(cell.attrib.get("r", "A1"))
                    while len(values) <= index:
                        values.append("")
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("m:v", NS)
                    value = "" if value_node is None else value_node.text or ""
                    if cell_type == "s" and value:
                        value = shared[int(value)]
                    elif cell_type == "inlineStr":
                        value = "".join(
                            node.text or ""
                            for node in cell.iter(f"{{{MAIN_NS}}}t")
                        )
                    values[index] = value
                rows.append(values)
            if not rows:
                result[sheet_name] = []
                continue
            headers = rows[0]
            result[sheet_name] = [
                {
                    header: values[index] if index < len(values) else ""
                    for index, header in enumerate(headers)
                    if header
                }
                for values in rows[1:]
                if any(values)
            ]
        return result


def product_from_row(
    row: dict[str, str],
    *,
    preset_key: str,
    row_index: int,
) -> dict[str, Any]:
    xcat1 = row.get("cate_level1_name", "").strip()
    xcat2 = row.get("cate_level2_name", "").strip()
    category = (
        row.get("commodity_name", "").strip()
        or xcat2
        or xcat1
    )
    ordercost = number(row.get("ordercost", ""))
    price = number(row.get("reserve_price", ""))
    return {
        "id": f"preset-{preset_key}-{row_index:02d}",
        "title": row.get("title", "").strip(),
        "category": category,
        "xcat1": xcat1,
        "xcat2": xcat2,
        "price": int(price) if price.is_integer() else price,
        "image": image_url(row.get("pict_url", "")),
        "ordercost": ordercost,
        "sales": f"{int(ordercost):,}人收藏" if ordercost else "情景精选",
        "attributes": list(dict.fromkeys(filter(None, (xcat1, xcat2, category)))),
        "baseScore": ordercost,
        "novelty": 0,
        "brand": "淘宝",
        "origin": "",
        "audiences": [],
        "styles": [],
        "goals": [],
        "trend": 0,
    }


def build(source_dir: Path) -> dict[str, Any]:
    workbook_cache: dict[str, dict[str, list[dict[str, str]]]] = {}
    presets: list[dict[str, Any]] = []
    for workbook_name, sheet_name, key, scenario, prompt in PRESET_SHEETS:
        sheets = workbook_cache.setdefault(
            workbook_name,
            workbook_rows(source_dir / workbook_name),
        )
        rows = sheets.get(sheet_name)
        if rows is None:
            raise ValueError(f"{workbook_name} 中缺少工作表 {sheet_name}")
        products = [
            product_from_row(row, preset_key=key, row_index=index)
            for index, row in enumerate(rows, start=1)
            if row.get("title", "").strip() and row.get("pict_url", "").strip()
        ]
        if not products:
            raise ValueError(f"{workbook_name}/{sheet_name} 没有可用商品")
        presets.append(
            {
                "key": key,
                "scenario": scenario,
                "prompt": prompt,
                "feedback": "已按当前情景为你更新推荐",
                "products": products,
            }
        )
    return {
        "version": "scenario-products-v1",
        "presets": presets,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = build(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts = {
        item["key"]: len(item["products"])
        for item in payload["presets"]
    }
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
