// Which backend API calls the RAIN v0.4 app makes in a real run, recorded from the browser's network traffic.
// Signs in, opens every persona (briefing), clicks its first briefing chip, types one of its queries, opens
// every sidebar page, plays both patient views, makes one write-back from a real button, and presses the
// footer Reset. Every request to /api/* or /health on the UI origin is recorded with its status, time and the
// backend's proof headers.
//   node scripts/e2e/api_usage_v4.mjs        (writes artifacts/rain-v4-validation/api_usage.json)
import { chromium } from "playwright-core";
import { writeFileSync } from "node:fs";

const BASE = process.env.RAIN_UI || "http://localhost:8184";
const OUT = new URL("../../artifacts/rain-v4-validation/api_usage.json", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const PERSONAS = Object.values((await (await fetch(`${BASE}/api/v4/ui/data?clientId=rain`)).json()).sections.constants.PERSONAS);
const QUERIES = (await (await fetch(`${BASE}/api/v4/queries`)).json()).queries;
const PACK_ID = { rain_linda: "patient_linda_garcia", rain_rosa: "patient_rosa_martinez", rain_hannah: "payer_hannah_lee" };

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
let step = "login";
const calls = [];
const started = new Map();
const isBackend = (u) => { const p = new URL(u); return p.origin === new URL(BASE).origin && (p.pathname.startsWith("/api/") || p.pathname === "/health"); };
page.on("request", (req) => { if (isBackend(req.url())) started.set(req, Date.now()); });
page.on("requestfinished", async (req) => {
  if (!started.has(req)) return;
  const res = await req.response();
  const h = res ? await res.allHeaders() : {};
  const u = new URL(req.url());
  calls.push({ step, method: req.method(), path: u.pathname, query: u.search, status: res?.status(), ms: Date.now() - started.get(req),
               body: req.postData()?.slice(0, 200) || null, dataSource: h["x-rain-data-source"] || null, turn: h["x-rain-turn"] || null,
               queryId: h["x-rain-query-id"] || null });
});
page.on("requestfailed", (req) => { if (started.has(req)) calls.push({ step, method: req.method(), path: new URL(req.url()).pathname, status: "failed", error: req.failure()?.errorText }); });

await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
const box = () => page.locator("textarea, input[type=text]").last();
let wrote = null;
for (const pid of PERSONAS) {
  step = `${pid}: open (briefing)`;
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const chip = (await (await fetch(`${BASE}/api/v4/ui/briefing?clientId=rain&personaId=${pid}`)).json()).chips?.[0];
  if (chip) {
    step = `${pid}: briefing chip`;
    const btn = page.getByRole("button", { name: chip, exact: true }).last();
    if (await btn.isVisible().catch(() => false)) await btn.click(); else { await box().fill(chip); await box().press("Enter"); }
    await page.waitForTimeout(2500);
  }
  const q = QUERIES.find((x) => x.persona === (PACK_ID[pid] || pid));
  if (q) {
    step = `${pid}: typed query ${q.id}`;
    await box().fill(q.question);
    await box().press("Enter");
    await page.waitForTimeout(3000);
  }
  const links = await page.$$eval("aside a[href], nav a[href]", (as) => [...new Set(as.map((a) => a.getAttribute("href")))]);
  for (const href of links) {
    if (!href || href.startsWith("http") || href.startsWith("/ask")) continue;
    step = `${pid}: page ${href}`;
    await page.goto(new URL(href, BASE).toString(), { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    // one write-back from a real button in a workbench (it is undone by the footer Reset at the end)
    if (!wrote) {
      const btn = page.locator("button:not([disabled])").filter({ hasText: /^\s*(Approve|Book|Sign off|Log)\b/ }).first();
      if (await btn.isVisible().catch(() => false)) {
        const label = (await btn.innerText()).trim().slice(0, 60);
        step = `${pid}: clicked "${label}" on ${href}`;
        await btn.click();
        await page.waitForTimeout(2500);
        wrote = step;
      }
    }
  }
}
for (const q of ["", "?patient=rosa"]) {
  step = `patient view /patient${q}`;
  await page.goto(`${BASE}/patient${q}`, { waitUntil: "networkidle" });
  const next = page.getByRole("button", { name: /Siguiente|Next/ }).last();
  for (let i = 0; i < 3; i++) { if (await next.isEnabled().catch(() => false)) await next.click(); await page.waitForTimeout(250); }
}
step = "footer Reset";
await page.goto(`${BASE}/ask?persona=rain_ceo`, { waitUntil: "networkidle" });
const reset = page.getByTitle("Reset every persona to the morning").first();
if (await reset.isVisible().catch(() => false)) { await reset.click(); await page.waitForTimeout(800);
  const confirm = page.getByRole("button", { name: /^(Reset|Restart|Yes|Confirm)/ }).last();
  if (await confirm.isVisible().catch(() => false)) await confirm.click();
  await page.waitForTimeout(3000); }
await browser.close();

// group by endpoint (path with ids replaced by their parameter names)
const template = (c) => c.path.replace(/^\/api\/v4\/queries\/[^/]+$/, "/api/v4/queries/{id}").replace(/^\/api\/v4\/ui\/actions\/[^/]+$/, "/api/v4/ui/actions/{actionId}");
const endpoints = {};
for (const c of calls) {
  const k = `${c.method} ${template(c)}`;
  const e = (endpoints[k] ||= { endpoint: k, calls: 0, statuses: {}, msTotal: 0, msMax: 0, dataSources: [], steps: [] });
  e.calls++; e.statuses[c.status] = (e.statuses[c.status] || 0) + 1; e.msTotal += c.ms || 0; e.msMax = Math.max(e.msMax, c.ms || 0);
  const ds = (c.dataSource || "").replace(/ \(query [^)]+\)/, " (query …)");
  if (ds && !e.dataSources.includes(ds)) e.dataSources.push(ds);
  const kind = c.step.replace(/^rain_\w+: /, "").replace(/ [A-Z]+-[SP]\d$/, "").replace(/ \/[^ ]+$/, "").replace(/clicked ".*"/, "clicked a workbench button");
  if (!e.steps.includes(kind)) e.steps.push(kind);
}
const summary = Object.values(endpoints).map((e) => ({ ...e, msAvg: Math.round(e.msTotal / e.calls), msTotal: undefined }));
writeFileSync(OUT, JSON.stringify({ base: BASE, personas: PERSONAS.length, wroteWith: wrote, totalCalls: calls.length, endpoints: summary, calls }, null, 1));
for (const e of summary) console.log(`${e.endpoint.padEnd(34)} ${String(e.calls).padStart(4)} calls  ${JSON.stringify(e.statuses)}  avg ${e.msAvg} ms  max ${e.msMax} ms  | ${e.steps.slice(0, 6).join("; ")}`);
console.log(`TOTAL ${calls.length} backend calls over ${PERSONAS.length} personas; write-back: ${wrote || "none clicked"}`);
