// Browser pass over every persona UI of the RAIN v0.3 app (http://localhost:8183):
// briefing render, every briefing chip -> expected answer text, every sidebar page, console errors.
import { chromium } from "playwright-core";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const BASE = "http://localhost:8183";
const FX = "C:/Users/pa613/RAIN/rain-api/fixtures/ultra_v3";
const OUT = new URL("./crawl/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });
const PERSONAS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access"];

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
let errors = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 160)); });
page.on("pageerror", (e) => errors.push("pageerror: " + e.message.slice(0, 160)));
const visible = async (text) => page.getByText(text, { exact: false }).first().isVisible().catch(() => false);
const errorBoundary = async () => /something went wrong|failed to render|unexpected error/i.test(await page.innerText("main").catch(() => ""));

await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
const report = {};
for (const pid of PERSONAS) {
  const fx = JSON.parse(readFileSync(`${FX}/${pid}.json`, "utf8"));
  const r = { name: fx.context.persona.name, briefing: null, chips: [], pages: [] };
  errors = [];
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const greet = fx.briefing.kpis?.[0]?.label || fx.briefing.chips?.[0];
  r.briefing = { ok: (await visible(greet)) && !(await errorBoundary()), greeting: greet };
  await page.screenshot({ path: `${OUT}${pid}-01-briefing.png` });

  // every briefing chip, from a fresh briefing each time
  for (const chip of fx.briefing.chips.map((c) => (typeof c === "string" ? c : c.label))) {
    const key = fx.match.chipToFlowKey[chip];
    const expected = (fx.turns[key]?.text || "").slice(0, 45);
    await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const before = errors.length;
    const btn = page.getByRole("button", { name: chip, exact: true }).last();
    let clicked = false;
    if (await btn.isVisible().catch(() => false)) { await btn.click(); clicked = true; }
    else { // chip not on screen as a button: type it, as a user would
      const box = page.locator("textarea, input[type=text]").last();
      await box.fill(chip); await box.press("Enter");
    }
    let ok = false;
    try { await page.getByText(expected, { exact: false }).first().waitFor({ timeout: 8000 }); ok = true; } catch {}
    ok = ok && !(await errorBoundary()) && errors.length === before;
    r.chips.push({ chip, flow: key, via: clicked ? "click" : "typed", ok, newErrors: errors.slice(before) });
  }
  await page.screenshot({ path: `${OUT}${pid}-02-last-answer.png` });

  // every page in this persona's sidebar
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  const links = await page.$$eval("aside a[href], nav a[href]", (as) =>
    [...new Map(as.map((a) => [a.getAttribute("href"), a.innerText.trim().replace(/\s+/g, " ")])).entries()]);
  for (const [href, text] of links) {
    if (!href || href.startsWith("http")) continue;
    const before = errors.length;
    const url = new URL(href, BASE);
    url.searchParams.set("persona", pid);
    await page.goto(url.toString(), { waitUntil: "networkidle" });
    await page.waitForTimeout(900);
    const h = await page.$$eval("main h1, main h2, header h1", (x) => x.map((e) => e.innerText.trim()).filter(Boolean).slice(0, 2));
    const ok = !(await errorBoundary()) && errors.length === before && (await page.innerText("main").catch(() => "")).length > 200;
    const slug = (text || href).toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 30);
    await page.screenshot({ path: `${OUT}${pid}-page-${slug}.png` });
    r.pages.push({ page: text, href, ok, headings: h, newErrors: errors.slice(before) });
  }
  report[pid] = r;
  const cOk = r.chips.filter((c) => c.ok).length, pOk = r.pages.filter((p) => p.ok).length;
  console.log(`${pid.padEnd(12)} ${r.name.slice(0, 26).padEnd(26)} briefing ${r.briefing.ok ? "OK" : "FAIL"} | chips ${cOk}/${r.chips.length} | pages ${pOk}/${r.pages.length} [${r.pages.map((p) => p.page).join(", ")}]`);
  for (const c of r.chips.filter((c) => !c.ok)) console.log("   chip FAIL:", c.chip, c.via, c.newErrors.join(" | "));
  for (const p of r.pages.filter((p) => !p.ok)) console.log("   page FAIL:", p.page, p.href, p.newErrors.join(" | "));
}
writeFileSync(`${OUT}crawl.json`, JSON.stringify(report, null, 1));
await browser.close();
