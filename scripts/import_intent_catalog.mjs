import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const source = process.argv[2];
const output = process.argv[3];
const sheetName = process.argv[4] || "Sheet2";
const scene = process.argv[5] || "camping";
const triggers = (process.argv[6] || "露营,野营,野炊").split(",").map((value) => value.trim()).filter(Boolean);
if (!source || !output) {
  throw new Error("Usage: node scripts/import_intent_catalog.mjs <source.xlsx> <output.json> [sheet] [scene] [triggers]");
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const rows = workbook.worksheets.getItem(sheetName).getUsedRange(true).values;
const headers = rows[0].map((value) => String(value ?? "").trim());
const positions = Object.fromEntries(headers.map((header, index) => [header, index]));
const required = ["item_id", "title", "ordercost", "cate_level1_name", "cate_level2_name", "pict_url", "reserve_price"];
for (const field of required) if (!(field in positions)) throw new Error(`Missing required column: ${field}`);

const asText = (value) => String(value ?? "").trim();
const asItemId = (value) => {
  const raw = asText(value);
  if (/^\d+(?:\.\d+)?[eE][+-]?\d+$/.test(raw)) return Number(raw).toFixed(0);
  return raw.replace(/\.0+$/, "");
};
const asNumber = (value) => {
  const parsed = Number(asText(value).replaceAll(",", ""));
  return Number.isFinite(parsed) ? parsed : 0;
};
const products = [];
for (const row of rows.slice(1)) {
  const itemId = asItemId(row[positions.item_id]);
  const title = asText(row[positions.title]);
  const xcat1 = asText(row[positions.cate_level1_name]);
  const xcat2 = asText(row[positions.cate_level2_name]);
  const commodity = positions.commodity_name === undefined ? "" : asText(row[positions.commodity_name]).replace(/^\\N$/, "");
  const category = positions.cate_name === undefined ? xcat2 : asText(row[positions.cate_name]);
  const pictUrl = asText(row[positions.pict_url]).replace(/^https?:\/\/img\.alicdn\.com\/imgextra\//, "").replace(/^\/+/, "");
  if (!itemId || !title || !pictUrl) continue;
  const ordercost = asNumber(row[positions.ordercost]);
  products.push({
    id: `intent-${scene}-${itemId}`, title, category: category || xcat2, xcat1, xcat2,
    price: asNumber(row[positions.reserve_price]),
    image: `https://img.alicdn.com/imgextra/${pictUrl}`,
    ordercost, sales: `${ordercost.toLocaleString("zh-CN")}人收藏`,
    attributes: [...new Set([scene, xcat1, xcat2, commodity, category].filter(Boolean))],
    baseScore: ordercost, novelty: 0, brand: "淘宝", origin: "",
    audiences: [], styles: [], goals: [scene], trend: 0,
  });
}
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.writeFile(output, `${JSON.stringify({ scene, triggers, products })}\n`);
console.log(`Imported ${products.length} ${scene} intent products.`);
