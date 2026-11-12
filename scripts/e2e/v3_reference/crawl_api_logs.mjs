// Per persona: which backend APIs the UI calls (console proof lines + window.__RAIN_API_CALLS__),
// which backend datasets each page shows (window.__RAIN_PAGE_DATA__), and rainQuery() from the console.
import { chromium } from "playwright-core";
import { readFileSync, writeFileSync } from "node:fs";

const BASE = "http://localhost:8183";
const OUT = new URL("./", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const FX = "C:/Users/pa613/RAIN/rain-api/fixtures/ultra_v3";
const PERSONAS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"];
const PREFIX = { rain_ceo: "CEO", rain_cmo: "CMO", rain_cio: "CIO", rain_state: "STATE", rain_chw: "CHW", rain_access: "ACCESS" };

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
let lines = [];
const errors = [];
page.on("console", async (m) => {
  if (m.type() === "error") errors.push(m.text().slice(0, 200));
  const args = await Promise.all(m.args().map((a) => a.jsonValue().catch(() => null)));
  if (typeof args[0] !== "string") return;
  const text = args[0].replace(/%c/g, "");
  if (!text.startsWith("RAIN")) return;
  lines.push(`[${m.type()}] ${text}`);
});

await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
const report = {};
for (const pid of PERSONAS) {
  lines = [];
  const fx = JSON.parse(readFileSync(`${FX}/${pid}.json`, "utf8"));
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  // one briefing chip → POST /ask
  const chip = typeof fx.briefing.chips[0] === "string" ? fx.briefing.chips[0] : fx.briefing.chips[0].label;
  const btn = page.getByRole("button", { name: chip, exact: true }).last();
  if (await btn.isVisible().catch(() => false)) await btn.click();
  await page.waitForTimeout(1500);
  // every sidebar page, navigated inside the app (no reload)
  const links = await page.$$eval("aside a[href], nav a[href]", (as) => [...new Set(as.map((a) => a.innerText.trim().replace(/\s+/g, " ")).filter(Boolean))]);
  for (const text of links) {
    await page.getByRole("link", { name: text, exact: true }).first().click().catch(() => {});
    await page.waitForLoadState("networkidle").catch(() => {});
    await page.waitForTimeout(900);
  }
  // run this persona's first synthetic and first public query from the browser console
  const ran = await page.evaluate(async (pfx) => {
    const out = [];
    for (const id of [`${pfx}-S1`, `${pfx}-P1`]) {
      const b = await window.rainQuery(id);
      out.push({ id, rows: b.rowCount, schema: b.schema, ms: b.ms });
    }
    return out;
  }, PREFIX[pid]);
  await page.waitForTimeout(500);
  const calls = await page.evaluate(() => window.__RAIN_API_CALLS__ || []);
  const pages = await page.evaluate(() => window.__RAIN_PAGE_DATA__ || {});
  const proof = await page.evaluate(() => { const p = window.__RAIN_DATA_PROOF__; return p && { url: p.url, requestId: p.requestId, server: p.server, verified: p.verified, dataSource: p.dataSource }; });
  report[pid] = { name: fx.context.persona.name, role: fx.context.persona.role, links, ran, calls, pages, proof, console: lines.slice() };
  console.log(`${pid}: ${calls.length} API calls after boot, ${Object.keys(pages).length} pages logged, ${lines.length} RAIN console lines, console queries ${ran.map((r) => `${r.id}=${r.rows} rows`).join(", ")}`);
}
writeFileSync(`${OUT}api_logs.json`, JSON.stringify(report, null, 1));
console.log("console errors:", errors.length ? errors : "none");
await browser.close();
