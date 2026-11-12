// Screenshot of the persona switcher, opened, and the persona names it lists (proof of the seven-persona roster).
//   node scripts/e2e/switcher_shot_v4.mjs     (writes artifacts/rain-v4-validation/crawl/persona-switcher.png)
import { chromium } from "playwright-core";

const BASE = process.env.RAIN_UI || "http://localhost:8184";
const OUT = new URL("../../artifacts/rain-v4-validation/crawl/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
await page.goto(`${BASE}/ask?persona=rain_ceo`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const trigger = page.locator("button", { hasText: "Gregory Haskins" }).first();
await trigger.click();
await page.waitForTimeout(600);
const names = ["Gregory Haskins", "Naomi Castellanos", "Raj Malhotra", "Lauren Pike", "Teresa Lopez", "Brandon Kee", "Linda Garcia",
  "Linda Hargrove", "Marcus Bell", "Denise Holloway", "Kayla Brooks", "Samuel Okafor", "Rosa Mart", "Hannah Lee"];
const listed = [];
for (const n of names) if (await page.getByText(n, { exact: false }).first().isVisible().catch(() => false)) listed.push(n);
await page.screenshot({ path: `${OUT}persona-switcher.png` });
console.log("visible in the open switcher:", listed.join(" | "));
await browser.close();
