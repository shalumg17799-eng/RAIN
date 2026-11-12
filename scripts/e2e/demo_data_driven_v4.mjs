// Open the CEO briefing in the real UI and report the PMPM KPI tiles (after a direct edit of synthetic source rows).
import { chromium } from "playwright-core";
const BASE = "http://localhost:8184";
const OUT = new URL("../../artifacts/rain-v4-validation/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const tag = process.argv[2] || "before";
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
let proof = "";
page.on("console", async (m) => {
  const a = await m.args()[0]?.jsonValue().catch(() => null);
  if (typeof a === "string" && a.includes("/api/v4/ui/data")) proof = a.replace(/%c/g, "");
});
await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
await page.goto(`${BASE}/ask?persona=rain_ceo`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const body = await page.innerText("main");
const tile = (label) => {
  const i = body.indexOf(label);
  return i < 0 ? "(not found)" : body.slice(i, i + 80).split("\n").slice(0, 3).join(" | ");
};
await page.screenshot({ path: `${OUT}data-driven-${tag}.png` });
console.log(`[${tag}] UI: ${tile("Actual vs. Expected PMPM")} || ${tile("Above Expected")}`);
console.log(`[${tag}] console: ${proof}`);
await browser.close();
