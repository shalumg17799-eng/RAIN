// The browser console shows backend API calls only. Signs in, opens a few personas, asks a question, runs a
// write-back and resets it, and records EVERY console message the app prints: each must be an API call entry
// (a collapsed "API <method> <path> → <status>" group, its details, and the group's end).
//   node scripts/e2e/console_check_v4.mjs
import { chromium } from "playwright-core";
const BASE = process.env.RAIN_UI || "http://localhost:8184";
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const all = [];
page.on("console", async (m) => {
  const first = await m.args()[0]?.jsonValue().catch(() => null);
  all.push({ type: m.type(), first: typeof first === "string" ? first.replace(/%c/g, "") : (first && typeof first === "object" ? "{details}" : String(first)), text: m.text().slice(0, 160) });
});
page.on("pageerror", (e) => all.push({ type: "pageerror", first: e.message, text: e.message }));
await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
for (const pid of ["rain_ceo", "rain_linda", "rain_hannah"]) {
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
}
await page.goto(`${BASE}/ask?persona=rain_ceo`, { waitUntil: "networkidle" });
const box = page.locator("textarea, input[type=text]").last();
await box.fill("Break down the gap");
await box.press("Enter");
await page.waitForTimeout(3000);
await page.evaluate(async () => {        // a write-back from the page itself (same code path as the store), then undo
  const res = await fetch("/api/v4/flow/reset", { method: "POST" });
  return res.status;
});
await page.waitForTimeout(500);
const isApi = (e) => (e.type === "startGroupCollapsed" && /^API (GET|POST) \//.test(e.first)) || (e.type === "log" && e.first === "{details}") || e.type === "endGroup";
const titles = all.filter((e) => e.type === "startGroupCollapsed").map((e) => e.first);
const other = all.filter((e) => !isApi(e));
console.log(`console messages: ${all.length}; API call entries: ${titles.length}; anything else: ${other.length}`);
const { writeFileSync, mkdirSync } = await import("node:fs");
const OUT = new URL("../../artifacts/rain-v4-validation/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });
writeFileSync(`${OUT}console_check.json`, JSON.stringify({ messages: all.length, apiCalls: titles.length, other: other.length, titles, otherMessages: other }, null, 1));
for (const t of titles.slice(0, 12)) console.log("  " + t);
for (const o of other) console.log("  OTHER", o.type, o.text);
await browser.close();
process.exit(other.length ? 1 : 0);
