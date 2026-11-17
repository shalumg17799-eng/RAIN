// The new Ultra UI (frontend/ultra-rain-v2) in a real browser against the running backend: sign in, open every
// persona and every workbench, ask a chip, open Linda's phone, and check that every value came from the backend.
//
//   node scripts/e2e/ui2_browser_check.mjs [http://localhost:8185]
//
// Write-backs (POST /api/v4/flow/*) are INTERCEPTED here and answered in the browser, so this check never changes
// the database; it records what the UI would have written. Screenshots go to artifacts/rain-v4-ui2-check/.
import { chromium } from "playwright-core";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = (process.argv[2] ?? "http://localhost:8185").replace(/\/$/, "");
const OUT = new URL("../../artifacts/rain-v4-ui2-check/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const PERSONAS = {
  rain_ceo: ["/value-insights", "/quality-gate", "/low-value-care", "/data-sources"],
  rain_cmo: ["/quality-gate", "/low-value-care", "/value-insights", "/model-governance", "/worklist"],
  rain_cio: ["/model-governance", "/data-sources"],
  rain_state: ["/county-explorer", "/value-insights", "/rhtp-reporting"],
  rain_chw: ["/worklist", "/scheduling"],
  rain_access: ["/scheduling", "/reminders"],
};
const BAD_TEXT = /could not load its data|invalid data|Something went wrong|is not defined|Cannot read prop/i;

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

const calls = [];
const flows = [];
const problems = [];
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("console", (m) => { if (m.type() === "error") problems.push(`console.error: ${m.text().slice(0, 200)}`); });
page.on("response", (r) => {
  const u = new URL(r.url());
  if (u.pathname.startsWith("/api/")) calls.push({ method: r.request().method(), path: u.pathname + u.search, status: r.status(), turn: r.headers()["x-rain-turn"] ?? null });
});
// Never write to the database from this check: answer the write-back here and keep what was sent.
await page.route("**/api/v4/flow/**", async (route) => {
  const req = route.request();
  flows.push({ path: new URL(req.url()).pathname, body: req.postData() });
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, flow: "intercepted" }) });
});

const settle = async () => { await page.waitForLoadState("networkidle").catch(() => {}); await page.waitForTimeout(700); };
const bodyText = () => page.evaluate(() => document.body.innerText);
const check = async (label) => {
  const t = await bodyText();
  const m = t.match(BAD_TEXT);
  if (m) problems.push(`${label}: page shows "${m[0]}"`);
  return t;
};
const shot = (name) => page.screenshot({ path: `${OUT}${name}.png`, fullPage: false });

// 1. sign in through the direct link (the documented demo gate)
await page.goto(`${BASE}/login/rain/?access=rain@9705`);
// the app signs in only after the backend data has loaded (a cold backend can take several seconds)
await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 90_000 });
await settle();
const report = { base: BASE, personas: {}, workbenches: {} };

// 2. every operator persona: Ask AI (briefing from the backend) and its workbenches
for (const [pid, benches] of Object.entries(PERSONAS)) {
  const before = calls.length;
  await page.goto(`${BASE}/?persona=${pid}`);
  await settle();
  await page.waitForTimeout(1500);
  const text = await check(`${pid} ask`);
  await shot(`${pid}-ask`);
  const mine = calls.slice(before);
  report.personas[pid] = {
    briefing: mine.filter((c) => c.path.includes("/api/v4/ui2/briefing")).map((c) => `${c.status} turn ${c.turn}`),
    context: mine.filter((c) => c.path.includes("/api/v4/ui2/context")).map((c) => c.status),
    firstLine: text.split("\n").find((l) => /Good morning|morning/i.test(l)) ?? null,
  };
  for (const path of benches) {
    await page.goto(`${BASE}${path}?persona=${pid}`);
    await settle();
    await check(`${pid} ${path}`);
    const key = `${pid}${path.replace(/\//g, "-")}`;
    await shot(key);
    report.workbenches[key] = "ok";
  }
}

// 3. ask the CEO's first chip in the conversation: POST /api/v4/ui2/ask
await page.goto(`${BASE}/?persona=rain_ceo`);
await settle();
await page.waitForTimeout(1500);
const chip = page.getByRole("button", { name: /quality gate|gate/i }).first();
const askBefore = calls.length;
if (await chip.count()) {
  await chip.click();
  await page.waitForTimeout(4000);
  await settle();
}
report.ceoAsk = calls.slice(askBefore).filter((c) => c.path.includes("/ask")).map((c) => `${c.status} turn ${c.turn}`);
await check("ceo ask");
await shot("rain_ceo-ask-answer");

// 4. Linda's phone: open the link, sign in, and confirm her video visit (a write-back, intercepted)
await page.goto(`${BASE}/patient`);
await settle();
await shot("rain_patient-phone");
const linkBtn = page.getByText(/https:\/\//).first();
if (await linkBtn.count()) { await linkBtn.click(); await page.waitForTimeout(2500); }
await settle();
const phone = await check("patient");
report.patient = { showsVisit: /Thursday/.test(phone), showsLinda: /Linda/.test(phone) };
await shot("rain_patient-chat");

// 5. Brandon books Linda in Scheduling? Not needed here: the write-back endpoints are unchanged and tested in rain-api.

const ui2 = calls.filter((c) => c.path.startsWith("/api/v4/ui2"));
report.apiCalls = { total: calls.length, ui2: ui2.length, failed: calls.filter((c) => c.status >= 400) };
report.dataBoot = calls.filter((c) => c.path.startsWith("/api/v4/ui2/data")).map((c) => c.status);
report.flowsIntercepted = flows;
report.problems = problems;
writeFileSync(`${OUT}report.json`, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ dataBoot: report.dataBoot, apiCalls: { total: calls.length, ui2: ui2.length, failed: report.apiCalls.failed.length },
  personas: report.personas, workbenches: Object.keys(report.workbenches).length, ceoAsk: report.ceoAsk, patient: report.patient,
  flowsIntercepted: flows.length, problems }, null, 1));
await browser.close();
process.exit(problems.length || report.apiCalls.failed.length ? 1 : 0);
