// Browser pass over every persona of the RAIN v0.4 app (http://localhost:8184), in the real UI:
// the briefing renders, every briefing chip reaches the answer the backend builds, every sidebar page
// renders, the patient thread plays, no removed persona can be opened, and the console shows the backend calls
// with no errors.
// Expected answers come from the live backend (POST /api/v4/ui/ask), not from fixtures.
//   node scripts/e2e/crawl_v4.mjs        (writes artifacts/rain-v4-validation/crawl/)
import { chromium } from "playwright-core";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.env.RAIN_UI || "http://localhost:8184";
const API = `${BASE}/api/v4/ui`;
const OUT = new URL("../../artifacts/rain-v4-validation/crawl/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });
// Every persona the backend serves (constants.PERSONAS, computed by rain-api/metrics_v4.py): 6 operators and the patient.
const PERSONAS = Object.values((await (await fetch(`${BASE}/api/v4/ui/data?clientId=rain`)).json()).sections.constants.PERSONAS);
const post = async (body) => (await fetch(`${API}/ask`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })).json();

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
let errors = [];
const proof = [];
page.on("console", async (m) => {
  if (m.type() === "error") errors.push(m.text().slice(0, 200));
  const a = await m.args()[0]?.jsonValue().catch(() => null);
  if (typeof a === "string" && /\/api\/v4\//.test(a)) proof.push(a.replace(/%c/g, "").slice(0, 400));
});
page.on("pageerror", (e) => errors.push("pageerror: " + e.message.slice(0, 200)));
const visible = async (text) => page.getByText(text, { exact: false }).first().isVisible().catch(() => false);
const broken = async () => /something went wrong|failed to render|unexpected error|couldn.t be rendered/i.test(await page.innerText("main").catch(() => ""));

await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
const report = { personas: {}, patients: {}, consoleProof: [] };
for (const pid of PERSONAS) {
  const briefing = await (await fetch(`${API}/briefing?clientId=rain&personaId=${pid}`)).json();
  const ctx = await (await fetch(`${API}/context?clientId=rain&personaId=${pid}`)).json();
  const r = { name: ctx.persona.name, briefing: null, chips: [], pages: [] };
  errors = [];
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const anchor = briefing.kpis?.[0]?.label || briefing.chips?.[0];
  r.briefing = { ok: (await visible(anchor)) && (await visible(ctx.persona.name.split(",")[0])) && !(await broken()), anchor };
  await page.screenshot({ path: `${OUT}${pid}-01-briefing.png` });

  for (const chip of briefing.chips) {
    const turn = await post({ clientId: "rain", personaId: pid, input: chip });
    const expected = (turn.text || "").slice(0, 45);
    await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    const before = errors.length;
    const btn = page.getByRole("button", { name: chip, exact: true }).last();
    let via = "typed";
    if (await btn.isVisible().catch(() => false)) { await btn.click(); via = "click"; }
    else { const box = page.locator("textarea, input[type=text]").last(); await box.fill(chip); await box.press("Enter"); }
    let ok = false;
    try { await page.getByText(expected, { exact: false }).first().waitFor({ timeout: 10000 }); ok = true; } catch {}
    ok = ok && !(await broken()) && errors.length === before;
    r.chips.push({ chip, turn: turn.id, via, ok, newErrors: errors.slice(before) });
  }
  await page.screenshot({ path: `${OUT}${pid}-02-last-answer.png` });

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
    // the patient view is a full-screen page with no app shell (<main>): read its body instead
    const text = (await page.innerText("main").catch(() => null)) ?? (await page.innerText("body").catch(() => ""));
    const ok = !(await broken()) && errors.length === before && text.length > 200;
    const slug = (text || href).toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 30);
    await page.screenshot({ path: `${OUT}${pid}-page-${slug}.png` });
    r.pages.push({ page: text, href, ok, newErrors: errors.slice(before) });
  }
  report.personas[pid] = r;
  const cOk = r.chips.filter((c) => c.ok).length, pOk = r.pages.filter((p) => p.ok).length;
  console.log(`${pid.padEnd(14)} ${r.name.slice(0, 24).padEnd(24)} briefing ${r.briefing.ok ? "OK" : "FAIL"} | chips ${cOk}/${r.chips.length} | pages ${pOk}/${r.pages.length} [${r.pages.map((p) => p.page).join(", ")}]`);
  for (const c of r.chips.filter((c) => !c.ok)) console.log("   chip FAIL:", c.chip, c.via, c.turn, c.newErrors.join(" | "));
  for (const p of r.pages.filter((p) => !p.ok)) console.log("   page FAIL:", p.page, p.href, p.newErrors.join(" | "));
}

for (const [who, q, marker] of [["linda", "", "Responda C para confirmar"]]) {
  errors = [];
  await page.goto(`${BASE}/patient${q}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const next = page.getByRole("button", { name: /Siguiente|Next/ }).last();
  for (let i = 0; i < 3; i++) { if (await next.isEnabled().catch(() => false)) await next.click(); await page.waitForTimeout(250); }
  const body = await page.innerText("body");
  const ok = body.includes(marker) && errors.length === 0 && !(await broken());
  await page.screenshot({ path: `${OUT}patient-${who}.png`, fullPage: true });
  report.patients[who] = { ok, errors: [...errors] };
  console.log(`patient ${who.padEnd(6)} ${ok ? "OK" : "FAIL"} ${errors.join(" | ")}`);
}
// The personas removed on 2026-11-10 are not served and cannot be opened: the app falls back to a served persona.
report.removed = {};
for (const [pid, name] of [["rain_hargrove", "Linda Hargrove"], ["rain_bell", "Marcus Bell"], ["rain_holloway", "Denise Holloway"],
                           ["rain_brooks", "Kayla Brooks"], ["rain_okafor", "Samuel Okafor"], ["rain_rosa", "Rosa Mart"],
                           ["rain_hannah", "Hannah Lee"]]) {
  const api = (await fetch(`${API}/briefing?clientId=rain&personaId=${pid}`)).status;
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const shown = await visible(name);
  report.removed[pid] = { api, shown, ok: api === 404 && !shown };
  console.log(`removed ${pid.padEnd(14)} api ${api} | name on screen ${shown ? "YES" : "no"} -> ${report.removed[pid].ok ? "OK" : "FAIL"}`);
}
report.consoleProof = proof.slice(0, 40);
writeFileSync(`${OUT}crawl.json`, JSON.stringify(report, null, 1));
const all = Object.values(report.personas);
console.log(`TOTAL briefings ${all.filter((r) => r.briefing.ok).length}/${all.length} | chips ${all.flatMap((r) => r.chips).filter((c) => c.ok).length}/${all.flatMap((r) => r.chips).length} | pages ${all.flatMap((r) => r.pages).filter((p) => p.ok).length}/${all.flatMap((r) => r.pages).length} | patients ${Object.values(report.patients).filter((p) => p.ok).length}/${Object.keys(report.patients).length} | removed personas blocked ${Object.values(report.removed).filter((r) => r.ok).length}/${Object.keys(report.removed).length}`);
console.log("console proof sample:", proof.slice(0, 3).join("\n   "));
await browser.close();
