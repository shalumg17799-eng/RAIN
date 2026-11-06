/**
 * Per-persona visual baseline: `npm run visual`.
 *
 *   npm run visual -- capture --out <dir> [--url http://localhost:4173]
 *       Screenshot every persona's briefing (docs/catalog/personas.json) in a
 *       1280 × 860 headless Chrome, signed in with the demo access link.
 *   npm run visual -- compare <baseDir> <headDir> [--out <diffDir>] [--threshold 0.5]
 *       Pixel-compare two captures; write a red-overlay diff per changed
 *       persona and a Markdown summary (diff/summary.md). Exits 1 when any
 *       persona changed by more than the threshold (% of pixels).
 *
 * Fonts render differently on each OS, so baselines are never committed: CI
 * captures the base branch and the pull request in the same runner and
 * compares those (.github/workflows/ultra-standard.yml, job `visual`). Locally,
 * capture before and after a change and compare the two.
 *
 * Chrome is found from $CHROME_PATH, then the usual install paths. The app must
 * already be served (`npm run build && npm run preview`). No dependencies: CDP
 * over Node's WebSocket, PNG through node:zlib.
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { inflateSync, deflateSync } from 'node:zlib';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const flag = (name, dflt) => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : dflt; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── PNG (8-bit RGB/RGBA, non-interlaced: what Chrome writes) ──────────────
function crcTable() { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; }
const CRC = crcTable();
const crc32 = (buf) => { let c = 0xffffffff; for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
export function decodePng(buf) {
  let pos = 8; let width = 0; let height = 0; let colorType = 0; const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos); const type = buf.toString('ascii', pos + 4, pos + 8); const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') { width = data.readUInt32BE(0); height = data.readUInt32BE(4); colorType = data[9]; if (data[8] !== 8 || data[12] !== 0) throw new Error('unsupported PNG'); }
    else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    pos += 12 + len;
  }
  const bpp = colorType === 6 ? 4 : colorType === 2 ? 3 : (() => { throw new Error(`PNG colour type ${colorType}`); })();
  const raw = inflateSync(Buffer.concat(idat)); const stride = width * bpp; const out = Buffer.alloc(width * height * 4);
  const prev = Buffer.alloc(stride); const line = Buffer.alloc(stride);
  for (let y = 0; y < height; y++) {
    const f = raw[y * (stride + 1)]; const src = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? line[x - bpp] : 0; const b = prev[x]; const c = x >= bpp ? prev[x - bpp] : 0;
      let v = src[x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c; const pa = Math.abs(p - a); const pb = Math.abs(p - b); const pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      line[x] = v & 0xff;
    }
    for (let x = 0; x < width; x++) { const o = (y * width + x) * 4; out[o] = line[x * bpp]; out[o + 1] = line[x * bpp + 1]; out[o + 2] = line[x * bpp + 2]; out[o + 3] = bpp === 4 ? line[x * bpp + 3] : 255; }
    line.copy(prev);
  }
  return { width, height, data: out };
}
export function encodePng({ width, height, data }) {
  const raw = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y++) { raw[y * (width * 4 + 1)] = 0; data.copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4); }
  const chunk = (type, d) => { const len = Buffer.alloc(4); len.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(type, 'ascii'), d]); const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td)); return Buffer.concat([len, td, crc]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4); ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}

// ── capture ──────────────────────────────────────────────────────────────
function findChrome() {
  const candidates = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  const hit = candidates.find((c) => c && existsSync(c));
  if (!hit) throw new Error('Chrome not found: set CHROME_PATH.');
  return hit;
}
async function capture() {
  const out = flag('out'); const url = flag('url', 'http://localhost:4173'); const access = process.env.VISUAL_ACCESS_KEY || 'rdvr@9705';
  if (!out) throw new Error('capture needs --out <dir>');
  mkdirSync(out, { recursive: true });
  const personas = JSON.parse(readFileSync(join(APP, 'docs/catalog/personas.json'), 'utf8'));
  const profile = mkdtempSync(join(tmpdir(), 'ultra-visual-'));
  const chrome = spawn(findChrome(), ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--force-device-scale-factor=1', 'about:blank'], { stdio: 'ignore' });
  let wsUrl = null;
  for (let i = 0; i < 100 && !wsUrl; i++) { await sleep(100); const f = join(profile, 'DevToolsActivePort'); if (existsSync(f)) { const [port, path] = readFileSync(f, 'utf8').trim().split('\n'); wsUrl = `ws://127.0.0.1:${port}${path}`; } }
  if (!wsUrl) throw new Error('Chrome did not start');
  const ws = new WebSocket(wsUrl); let id = 0; const pending = new Map();
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); } };
  await new Promise((r) => (ws.onopen = r));
  const send = (method, params = {}, sessionId) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });
  const queue = [...personas]; const log = []; const blank = [];
  const worker = async () => {
    const { result: { browserContextId } } = await send('Target.createBrowserContext', { disposeOnDetach: true });
    const { result: { targetId } } = await send('Target.createTarget', { url: 'about:blank', browserContextId });
    const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
    const s = (m, p) => send(m, p, sessionId);
    await s('Page.enable'); await s('Runtime.enable');
    await s('Emulation.setDeviceMetricsOverride', { width: 1280, height: 860, deviceScaleFactor: 1, mobile: false });
    // A background tab never runs its animations to the end; make this one count as focused.
    await s('Emulation.setFocusEmulationEnabled', { enabled: true });
    let client = null;
    while (queue.length) {
      const { client: c, persona } = queue.shift();
      if (client !== c) {
        await s('Page.navigate', { url: `${url}/?access=${encodeURIComponent(access)}` }); await sleep(2500);
        await s('Runtime.evaluate', { expression: `localStorage.setItem('selected_client', ${JSON.stringify(c)})` });
        client = c;
      }
      await s('Page.navigate', { url: `${url}/ask?persona=${encodeURIComponent(persona)}` }); await sleep(6000);
      const r = await s('Page.captureScreenshot', { format: 'png' });
      const png = Buffer.from(r.result.data, 'base64');
      writeFileSync(join(out, `${c}~${persona}.png`), png);
      if (isBlank(decodePng(png))) blank.push(`${c}/${persona}`);
      log.push(`${c}/${persona}`);
    }
  };
  await Promise.all(Array.from({ length: +flag('workers', '4') }, worker));
  ws.close();
  // Let Chrome finish writing its profile before removing it; cleanup never fails the run.
  await new Promise((r) => { chrome.once('exit', r); chrome.kill(); setTimeout(r, 5000); });
  try { rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* a temp dir */ }
  console.log(`Captured ${log.length} personas into ${out}`);
  // A blank page means the app did not render (a stale dev server, a failed
  // build, a sign-in that did not take): every comparison would then "pass".
  if (blank.length) { console.error(`Blank captures (the app did not render): ${blank.join(', ')}`); process.exit(1); }
}

/** True when the screenshot is (nearly) one colour. */
function isBlank({ data }) {
  let min = 255; let max = 0;
  for (let i = 0; i < data.length; i += 4 * 97) { const l = (data[i] + data[i + 1] + data[i + 2]) / 3; if (l < min) min = l; if (l > max) max = l; }
  return max - min < 24;
}

// ── compare ──────────────────────────────────────────────────────────────
function compare() {
  const [baseDir, headDir] = args.slice(1).filter((a, i, all) => !a.startsWith('--') && !(all[i - 1] || '').startsWith('--'));
  const out = flag('out', join(headDir, '..', 'visual-diff')); const threshold = +flag('threshold', '0.5');
  mkdirSync(out, { recursive: true });
  const names = [...new Set([...readdirSync(baseDir), ...readdirSync(headDir)])].filter((n) => n.endsWith('.png')).sort();
  const rows = []; let failed = 0;
  for (const n of names) {
    const label = n.replace('.png', '').replace('~', ' / ');
    if (!existsSync(join(baseDir, n))) { rows.push(`| ${label} | new | — |`); continue; }
    if (!existsSync(join(headDir, n))) { rows.push(`| ${label} | removed | — |`); continue; }
    const a = decodePng(readFileSync(join(baseDir, n))); const b = decodePng(readFileSync(join(headDir, n)));
    if (a.width !== b.width || a.height !== b.height) { rows.push(`| ${label} | size changed | — |`); failed++; continue; }
    const diff = Buffer.from(b.data); let changed = 0;
    for (let i = 0; i < a.data.length; i += 4) {
      const d = Math.max(Math.abs(a.data[i] - b.data[i]), Math.abs(a.data[i + 1] - b.data[i + 1]), Math.abs(a.data[i + 2] - b.data[i + 2]));
      if (d > 12) { changed++; diff[i] = 220; diff[i + 1] = 0; diff[i + 2] = 60; diff[i + 3] = 255; }
      else { diff[i] = 255 - ((255 - b.data[i]) * 0.4); diff[i + 1] = 255 - ((255 - b.data[i + 1]) * 0.4); diff[i + 2] = 255 - ((255 - b.data[i + 2]) * 0.4); }
    }
    const pct = (100 * changed) / (a.width * a.height);
    if (changed) writeFileSync(join(out, n), encodePng({ width: b.width, height: b.height, data: diff }));
    if (pct > threshold) failed++;
    rows.push(`| ${label} | ${pct.toFixed(2)}% | ${pct > threshold ? 'over threshold' : changed ? 'within threshold' : 'identical'} |`);
  }
  const summary = [`## Visual baseline: ${names.length} personas, ${failed} over ${threshold}% changed`, '', '| Persona | Pixels changed | Result |', '|---|---:|---|', ...rows, ''].join('\n');
  writeFileSync(join(out, 'summary.md'), summary);
  console.log(summary);
  process.exit(failed ? 1 : 0);
}

const cmd = args[0];
if (cmd === 'capture') await capture();
else if (cmd === 'compare') compare();
else { console.error('usage: npm run visual -- capture --out <dir> | compare <baseDir> <headDir>'); process.exit(2); }
