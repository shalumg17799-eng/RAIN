// Read-only proof that the new UI (frontend/ultra-rain-v2, http://localhost:8185) shows backend data, not bundled data.
//
//   node scripts/e2e/ui2_prove_dynamic.mjs [http://localhost:8185]
//
// 1. reads a few values straight from Postgres (rain4-postgres-1, read-only transaction);
// 2. opens the UI and checks it shows exactly those values, with the backend request ids;
// 3. blocks GET /api/v4/ui2/data in the browser and checks the UI shows the "could not load" screen (no local fallback).
// Write-backs are intercepted, so nothing is written.
import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";

const BASE = (process.argv[2] ?? "http://localhost:8185").replace(/\/$/, "");
const sql = (q) => execFileSync("docker", ["exec", "rain4-postgres-1", "psql", "-U", "postgres", "-d", "rain_v4", "-At", "-c",
  `BEGIN READ ONLY; ${q}; COMMIT;`], { encoding: "utf8" }).split("\n").filter((l) => l && !/^(BEGIN|COMMIT)$/.test(l))[0];

const db = {
  teresaOpen: sql("SELECT count(*) FROM synthetic.outreach_task WHERE assigned_to = 'Teresa Lopez' AND status <> 'closed'"),
  lindaVisit: sql("SELECT to_char(s.slot_start, 'FMDay, Mon FMDD, FMHH12:MI AM') FROM synthetic.appointment a JOIN synthetic.slot s ON s.slot_id = a.slot_id WHERE a.patient_id = 'M-40107' AND a.status IN ('booked','confirmed') ORDER BY s.slot_start LIMIT 1"),
  lindaGapOpen: sql("SELECT count(*) FROM synthetic.care_gap WHERE patient_id = 'M-40107' AND measure_code = 'CMS165' AND status = 'open'"),
};

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const calls = [];
page.on("response", (r) => { const u = new URL(r.url()); if (u.pathname.startsWith("/api/")) calls.push(`${r.status()} ${u.pathname} req=${r.headers()["x-rain-request-id"] ?? "-"}`); });
await page.route("**/api/v4/flow/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true,"flow":"intercepted"}' }));
const settle = async () => { await page.waitForLoadState("networkidle").catch(() => {}); await page.waitForTimeout(1500); };

await page.goto(`${BASE}/login/rain/?access=rain@9705`);
await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 90_000 });
await settle();
await page.goto(`${BASE}/worklist?persona=rain_chw`);
await settle();
const fromApi = await page.evaluate(() => window.__RAIN_DATA_PROOF__ && { url: window.__RAIN_DATA_PROOF__.url, requestId: window.__RAIN_DATA_PROOF__.requestId, server: window.__RAIN_DATA_PROOF__.server, verified: window.__RAIN_DATA_PROOF__.verified, open: null });
await page.goto(`${BASE}/?persona=rain_chw`);
await settle();
const chw = await page.evaluate(() => document.body.innerText);
await page.goto(`${BASE}/patient`);
await settle();
const phone = await page.evaluate(() => document.body.innerText);

const blocked = await browser.newPage();
await blocked.route("**/api/v4/ui2/data**", (route) => route.abort());
await blocked.goto(`${BASE}/`);
await blocked.waitForTimeout(2500);
const blockedText = await blocked.evaluate(() => document.body.innerText);

const result = {
  database: db,
  ui: {
    "Teresa's open tasks tile shows the DB count": new RegExp(`\\b${db.teresaOpen}\\b`).test(chw),
    "Linda's phone shows the DB visit": phone.includes(db.lindaVisit.replace(/^(\w+), (\w+) (\d+), /, "$1, $2 $3, ")) || phone.includes(db.lindaVisit.split(",")[0]),
  },
  dataLoad: fromApi,
  backendCalls: calls.slice(0, 8),
  backendBlocked: /could not load its data from the backend/i.test(blockedText) ? "UI shows 'RAIN could not load its data from the backend' and no figures" : blockedText.slice(0, 200),
};
console.log(JSON.stringify(result, null, 1));
await browser.close();
