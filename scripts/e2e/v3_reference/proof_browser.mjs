// Browser proof: console output, network requests, the proof object, and live values on screen.
import { chromium } from "playwright-core";
import { mkdirSync, writeFileSync } from "node:fs";
const BASE = "http://localhost:8183";
const OUT = new URL("./proof/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });
const mode = process.argv[2] || "live";

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 950 } })).newPage();
const consoleLines = [];
page.on("console", async (m) => {
  // render console.table / group args the way devtools would print them
  const args = await Promise.all(m.args().map((a) => a.jsonValue().catch(() => "?")));
  const text = typeof args[0] === "string" ? args[0].replace(/%c/g, "") : m.text();
  const rest = args.slice(1).filter((a) => typeof a !== "string" || !/^(background|color|font-weight)|^$/.test(a));
  consoleLines.push(`[${m.type()}] ${text}${rest.length ? " " + JSON.stringify(rest).slice(0, 900) : ""}`);
});
const requests = [];
page.on("request", (r) => requests.push(`${r.method()} ${r.url().replace(BASE, "")}`));

const t0 = Date.now();
await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: mode === "down" ? "load" : "networkidle" });
if (mode !== "down") await page.waitForTimeout(1500);

if (mode === "down") {
  await page.getByText("could not load its data from the backend").waitFor({ timeout: 30000 });
  console.log(`error screen shown after ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  await page.screenshot({ path: `${OUT}backend-down.png` });
  console.log("PAGE TEXT:", (await page.innerText("body")).slice(0, 500));
} else {
  const proof = await page.evaluate(() => {
    const p = window.__RAIN_DATA_PROOF__;
    return p && { url: p.url, status: p.status, source: p.source, server: p.server, requestId: p.requestId, dataSource: p.dataSource,
      verified: p.verified, sha256Header: p.sha256Header, sha256Computed: p.sha256Computed, bytes: p.bytes, ms: p.ms, loadedAt: p.loadedAt, keysRead: p.keysRead.length };
  });
  console.log("window.__RAIN_DATA_PROOF__ =", JSON.stringify(proof, null, 1));
  await page.screenshot({ path: `${OUT}ceo-briefing.png` });
  // a chat call, to show the per-call proof line
  const box = page.locator("textarea, input[type=text]").last();
  await box.fill("Break down the gap"); await box.press("Enter");
  await page.waitForTimeout(3000);
  // State persona: County Explorer with live public values
  await page.goto(`${BASE}/county-explorer?persona=rain_state`, { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(1200);
  if (!page.url().includes("county")) {
    await page.goto(`${BASE}/ask?persona=rain_state`, { waitUntil: "networkidle" });
    await page.getByText("County Explorer", { exact: true }).first().click();
    await page.waitForLoadState("networkidle"); await page.waitForTimeout(1200);
  }
  const table = await page.$$eval("table tr", (rows) => rows.map((r) => [...r.querySelectorAll("th,td")].map((c) => c.innerText.trim()).join(" | ")).filter(Boolean).slice(0, 8));
  console.log("COUNTY EXPLORER TABLE (" + page.url().replace(BASE, "") + "):\n  " + table.join("\n  "));
  const caption = await page.getByText("live public data served by the backend", { exact: false }).first().innerText().catch(() => "(caption not found)");
  console.log("CAPTION:", caption.slice(0, 220));
  await page.screenshot({ path: `${OUT}state-county-explorer.png`, fullPage: true });
  const calls = await page.evaluate(() => (window.__RAIN_API_CALLS__ || []).map((c) => `${c.method} ${c.url} ${c.status} turn=${c.turn} source=${c.source} server=${c.server} req=${c.requestId}`));
  console.log("window.__RAIN_API_CALLS__:", JSON.stringify(calls, null, 1));
}
console.log("\nCONSOLE OUTPUT (" + consoleLines.length + " lines):\n" + consoleLines.join("\n"));
const api = requests.filter((r) => r.includes("/api/"));
const chunks = requests.filter((r) => r.includes("/assets/") && r.endsWith(".js")).map((r) => r.split("/assets/")[1]);
console.log("\nAPI REQUESTS:", JSON.stringify(api, null, 1));
console.log("JS CHUNKS LOADED:", chunks.join(", "));
writeFileSync(`${OUT}console-${mode}.txt`, consoleLines.join("\n"));
await browser.close();
