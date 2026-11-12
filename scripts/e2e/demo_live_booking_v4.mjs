// The live demo of dynamic data, clicked in the real UI with two separate browsers (no SQL):
//   browser A = Brandon Kee books a waiting patient in Scheduling (POST /api/v4/flow/book writes Postgres rows);
//   browser B = Teresa Lopez, a different browser session, reloads and her "Booked" tile has moved;
//   then "Reset demo" undoes the rows and both tiles are back.
//   node scripts/e2e/demo_live_booking_v4.mjs     (screenshots in artifacts/rain-v4-validation/demo-booking-*.png)
import { chromium } from "playwright-core";

const BASE = process.env.RAIN_UI || "http://localhost:8184";
const OUT = new URL("../../artifacts/rain-v4-validation/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });

async function session() {
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await page.goto(`${BASE}/login/rain/?access=rain@9705`, { waitUntil: "networkidle" });
  return page;
}
async function tile(page, persona, label) {
  await page.goto(`${BASE}/ask?persona=${persona}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const lines = (await page.innerText("main")).split("\n").map((s) => s.trim()).filter(Boolean);
  const i = lines.findIndex((l) => l === label);
  return i < 0 ? "(not found)" : lines[i + 1];
}

const kee = await session();       // browser A
const teresa = await session();    // browser B (its own cookies and storage)
await fetch(`${BASE}/api/v4/flow/reset`, { method: "POST" });

const before = { keeWaiting: await tile(kee, "rain_access", "Bookings waiting"), teresaBooked: await tile(teresa, "rain_chw", "Booked") };
console.log("before   Kee 'Bookings waiting' =", before.keeWaiting, "| Teresa 'Booked' =", before.teresaBooked);
await teresa.screenshot({ path: `${OUT}demo-booking-1-teresa-before.png` });

// Browser A: Brandon books the first waiting patient with active coverage into the first open slot.
await kee.goto(`${BASE}/scheduling?persona=rain_access`, { waitUntil: "networkidle" });
await kee.waitForTimeout(1000);
// (Linda Garcia is the scripted patient story, so the demo books someone else.)
const patient = kee.locator("li button").filter({ hasNotText: "Lapsed" }).filter({ hasNotText: "Linda Garcia" }).first();
const who = (await patient.innerText()).split("\n")[0];
await patient.click();
await kee.waitForTimeout(500);
// the open slots render as cards at this width (rows of a table on a wide pane): click the first one
await kee.locator("main button").filter({ hasText: "Mode" }).first().click();
await kee.getByRole("button", { name: "Confirm booking" }).click();
await kee.waitForTimeout(2500);
await kee.screenshot({ path: `${OUT}demo-booking-2-kee-booked.png` });
console.log(`booked   Brandon Kee confirmed a visit for ${who} in the UI`);

const after = { keeWaiting: await tile(kee, "rain_access", "Bookings waiting"), teresaBooked: await tile(teresa, "rain_chw", "Booked") };
console.log("after    Kee 'Bookings waiting' =", after.keeWaiting, "| Teresa 'Booked' =", after.teresaBooked, "(browser B only reloaded)");
await teresa.screenshot({ path: `${OUT}demo-booking-3-teresa-after.png` });

// Reset demo (the footer button posts /api/v4/flow/reset); browser B reloads again.
const reset = kee.getByRole("button", { name: /Reset demo/ });
if (await reset.isVisible().catch(() => false)) { await reset.click(); await kee.waitForTimeout(2000); }
else await fetch(`${BASE}/api/v4/flow/reset`, { method: "POST" });
const restored = { keeWaiting: await tile(kee, "rain_access", "Bookings waiting"), teresaBooked: await tile(teresa, "rain_chw", "Booked") };
console.log("reset    Kee 'Bookings waiting' =", restored.keeWaiting, "| Teresa 'Booked' =", restored.teresaBooked);

const ok = after.teresaBooked !== before.teresaBooked && after.keeWaiting !== before.keeWaiting
  && restored.teresaBooked === before.teresaBooked && restored.keeWaiting === before.keeWaiting;
console.log(ok ? "PASS: a click in one browser changed the database, the other browser saw it, Reset undid it" : "FAIL");
await browser.close();
process.exit(ok ? 0 : 1);
