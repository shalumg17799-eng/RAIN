// Linda's phone on the new UI asks her data questions live: her records (synthetic) and her county (public data).
//
//   node scripts/e2e/ui2_patient_queries_check.mjs [http://localhost:8185]
//
// Opens /patient, signs in through her text link, then types and taps questions and checks each answer came from the
// backend (POST /api/v4/ui2/ask → query:GAR-*). Write-backs (/api/v4/flow) are intercepted, so nothing is written.
// Screenshots: artifacts/rain-v4-ui2-check/patient-*.png
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const BASE = (process.argv[2] ?? "http://localhost:8185").replace(/\/$/, "");
const OUT = new URL("../../artifacts/rain-v4-ui2-check/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const asks = [];
page.on("response", async (r) => {
  if (r.url().includes("/api/v4/ui2/ask") && r.request().method() === "POST") {
    asks.push({ sent: JSON.parse(r.request().postData() ?? "{}").input, status: r.status(), turn: r.headers()["x-rain-turn"], source: r.headers()["x-rain-data-source"] });
  }
});
await page.route("**/api/v4/flow/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true,"flow":"intercepted"}' }));

await page.goto(`${BASE}/login/rain/?access=rain@9705`);
await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 90_000 });
await page.goto(`${BASE}/patient`);
await page.waitForLoadState("networkidle");
await page.getByText(/https:\/\//).first().click();
await page.waitForTimeout(2500);
await page.waitForSelector("#linda-ask", { timeout: 30_000 });

const chips = await page.locator("text=Ask about your records and your county").count();
const input = page.locator("#linda-ask");
const results = [];
async function typeAndWait(text) {
  const before = asks.length;
  await input.fill(text);
  await input.press("Enter");
  await page.waitForTimeout(400);
  await page.waitForFunction(() => !document.body.innerText.includes("Checking your records"), null, { timeout: 30_000 });
  await page.waitForTimeout(500);
  const asked = asks.slice(before);
  results.push({ typed: text, backend: asked.map((a) => `${a.status} ${a.turn} ← ${a.source}`) });
}
await typeAndWait("Is my county a primary care shortage area?");
await page.screenshot({ path: `${OUT}patient-public-query.png` });
await typeAndWait("GAR-P2");
await typeAndWait("What are my home blood pressure readings?");
await page.screenshot({ path: `${OUT}patient-synthetic-query.png` });
await typeAndWait("how far is the nearest health center");
await typeAndWait("CEO-S1");
await typeAndWait("When is my next visit?");
// tap one of the records chips
const before = asks.length;
await page.getByRole("button", { name: "Which care gaps are open for me?" }).first().click();
await page.waitForTimeout(2500);
results.push({ tapped: "Which care gaps are open for me?", backend: asks.slice(before).map((a) => `${a.status} ${a.turn}`) });
await page.screenshot({ path: `${OUT}patient-chip-query.png` });
const tables = await page.locator("table").count();
console.log(JSON.stringify({ recordsChipsShown: chips > 0, results, tablesOnPhone: tables }, null, 1));
await browser.close();
