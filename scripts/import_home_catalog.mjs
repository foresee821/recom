import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const source = process.argv[2];
const output = process.argv[3];
if (!source || !output) throw new Error("Usage: node scripts/import_home_catalog.mjs <source.xlsx> <output.json>");

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const rows = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
const headers = rows[0].map((value) => String(value ?? "").trim());
const positions = Object.fromEntries(headers.map((header, index) => [header, index]));
const required = ["item_id", "title", "ordercost", "cate_level1_name", "cate_level2_name", "pict_url", "reserve_price"];
for (const field of required) if (!(field in positions)) throw new Error(`Missing required column: ${field}`);

const excludedItemIds = new Set([
  "103359918",
  "158364381",
  "41986869647",
  "43789563103",
  "89934541",
  "750171245001",
]);

const asText = (value) => String(value ?? "").trim();
const asNumber = (value) => {
  const parsed = Number(asText(value).replaceAll(",", ""));
  return Number.isFinite(parsed) ? parsed : 0;
};
const products = [];
const seen = new Set();
for (const row of rows.slice(1)) {
  const itemId = asText(row[positions.item_id]);
  const title = asText(row[positions.title]);
  const xcat1 = asText(row[positions.cate_level1_name]);
  const xcat2 = asText(row[positions.cate_level2_name]);
  const pictUrl = asText(row[positions.pict_url]).replace(/^https?:\/\/img\.alicdn\.com\/imgextra\//, "").replace(/^\/+/, "");
  if (!itemId || !title || !xcat2 || !pictUrl || title.includes("测试商品请不要拍") || seen.has(itemId) || excludedItemIds.has(itemId)) continue;
  seen.add(itemId);
  const ordercost = asNumber(row[positions.ordercost]);
  products.push({
    id: `item-${itemId}`, title, category: xcat2, xcat1, xcat2,
    price: asNumber(row[positions.reserve_price]),
    image: `https://img.alicdn.com/imgextra/${pictUrl}`,
    ordercost, sales: `${ordercost.toLocaleString("zh-CN")}人收藏`,
    attributes: [xcat1, xcat2], baseScore: ordercost, novelty: 0,
    brand: "淘宝", origin: "", audiences: [], styles: [], goals: [], trend: 0,
  });
}
products.sort((left, right) => right.ordercost - left.ordercost || left.id.localeCompare(right.id));
await fs.mkdir(path.dirname(output), { recursive: true });
await fs.writeFile(output, `${JSON.stringify({ version: "20260720", products })}\n`);
console.log(`Imported ${products.length} products from ${rows.length - 1} rows.`);
