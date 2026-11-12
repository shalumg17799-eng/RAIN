// Type every persona query's question into that persona's chat in the real UI; check the live table renders.
import { chromium } from "playwright-core";
import { writeFileSync } from "node:fs";

const BASE = process.env.RAIN_UI || "http://localhost:8184";
const OUT = new URL("../../artifacts/rain-v4-validation/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const PERSONAS = ["rain_ceo", "rain_cmo", "rain_cio", "rain_state", "rain_chw", "rain_access", "rain_linda"];
// The patient keeps her own id in the query pack (rain-api/persona_queries_v4.py PERSONA_ALIASES).
const PACK_ID = { rain_linda: "patient_linda_garcia" };
const list = await (await fetch(`${BASE}/api/v4/queries`)).json();

const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
const consoleLines = [];
const errors = [];
page.on("console", async (m) => {
  if (m.type() === "error") errors.push(m.text().slice(0, 200));
  const a = await m.args()[0]?.jsonValue().catch(() => null);
  if (typeof a === "string" && a.includes("/api/v4/ui/ask")) consoleLines.push(a.replace(/%c/g, ""));
});
await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });

const results = [];
for (const pid of PERSONAS) {
  await page.goto(`${BASE}/ask?persona=${pid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  for (const q of list.queries.filter((x) => x.persona === (PACK_ID[pid] ?? pid))) {
    const before = consoleLines.length;
    const box = page.locator("textarea, input[type=text]").last();
    await box.fill(q.question);
    await box.press("Enter");
    const caption = page.getByText(`${q.id} · rain_v4`, { exact: false }).last();
    let ok = false, rows = 0, text = "";
    try {
      await caption.waitFor({ timeout: 15000 });
      ok = true;
      // the data_table right after its caption: count its body rows
      rows = await caption.evaluate((el) => {
        const card = el.closest("div[class]")?.parentElement ?? el.parentElement;
        const t = card?.querySelector("table") ?? document.querySelectorAll("table")[document.querySelectorAll("table").length - 1];
        return t ? t.querySelectorAll("tbody tr").length : 0;
      });
      text = (await page.locator("main").innerText()).split(q.question).pop().slice(0, 160).replace(/\n+/g, " | ");
    } catch { /* not rendered */ }
    await page.waitForTimeout(300);
    const line = consoleLines.slice(before).find((l) => l.includes(`turn query:${q.id}`)) ?? "";
    results.push({ id: q.id, persona: pid, data: q.data, question: q.question, rendered: ok, rows, consoleLine: line, answer: text });
    if (q.id === "HAR-P3") await page.screenshot({ path: `${OUT}chat-HAR-P3.png` });
    if (q.id === "BEL-P5") await page.screenshot({ path: `${OUT}chat-BEL-P5.png` });
  }
  const mine = results.filter((r) => r.persona === pid);
  console.log(`${pid}: ${mine.filter((r) => r.rendered && r.rows > 0 && r.consoleLine).length}/${mine.length} rendered live tables`);
}
writeFileSync(`${OUT}chat_queries.json`, JSON.stringify(results, null, 1));
const ok = results.filter((r) => r.rendered && r.rows > 0 && r.consoleLine).length;
console.log(`TOTAL ${ok}/${results.length} | console errors: ${errors.length ? errors.join(" / ") : "none"}`);
for (const r of results.filter((r) => !(r.rendered && r.rows > 0 && r.consoleLine))) console.log("FAIL", r.id, r.rendered, r.rows, r.consoleLine.slice(0, 80));
console.log("example console line:", results[0].consoleLine);
await browser.close();
