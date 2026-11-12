// Type public-data questions into the real UI and capture what is shown.
import { chromium } from "playwright-core";
const BASE = "http://localhost:8183";
const OUT = new URL("./public/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
import { mkdirSync } from "node:fs"; mkdirSync(OUT, { recursive: true });
const CASES = [
  ["rain_ceo", "What is the hypertension rate in Elko County?"],
  ["rain_state", "What is the social vulnerability index for Pershing County?"],
  ["rain_access", "Where are the health center sites?"],
];
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
const calls = [];
page.on("request", (r) => { if (r.url().includes("/api/")) calls.push(`${r.method()} ${r.url().replace(BASE, "")}`); });
await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
for (const [pid, q] of CASES) {
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const box = page.locator("textarea, input[type=text]").last();
  await box.fill(q); await box.press("Enter");
  await page.waitForTimeout(3500);
  const body = await page.innerText("main");
  const i = body.lastIndexOf(q);
  const ans = body.slice(i + q.length, i + q.length + 700).replace(/\n+/g, " | ");
  const slug = pid + "-" + q.toLowerCase().replace(/[^a-z]+/g, "-").slice(0, 40);
  await page.screenshot({ path: `${OUT}${slug}.png` });
  console.log(`\n[${pid}] ${q}\n  shown: ${ans.slice(0, 420)}\n  screenshot: ${OUT}${slug}.png`);
  if (pid === "rain_state") {
    const row = (await page.innerText("main")).split("\n").filter((l) => /Pershing/.test(l)).slice(0, 4);
    console.log("  Pershing lines on screen:", JSON.stringify(row));
  }
}
console.log("\nAPI calls made by the UI:", JSON.stringify([...new Set(calls.map((c) => c.split("?")[0]))]));
await browser.close();
