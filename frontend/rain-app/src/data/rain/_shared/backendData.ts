/**
 * The RAIN UI's only data source: the backend.
 *
 * Every number, record, dataset, map shape, source and persona contract the UI
 * shows is fetched once at boot from `GET {VITE_ULTRA_API_BASE}/data?clientId=rain`
 * (rain-api `ui_data_v3.py`: Postgres `rain_v3.ui_v3.dataset`, with the county
 * public figures computed live from `rain_v3.public_data`). Nothing is bundled:
 * the data modules in this folder read from here, and reading before the
 * backend has answered throws instead of falling back to anything local.
 *
 * Proof is printed to the browser console and kept on `window.__RAIN_DATA_PROOF__`:
 * the request, the backend's proof headers, and the SHA-256 of the body as
 * sent by the server (X-RAIN-Data-Sha256) against the one computed here.
 */

import { PROOF_STYLE, proof as log } from '@core/log';
import { logBackendCall } from '@core/api/proof';

export type SectionName = 'contracts' | 'personas' | 'constants' | 'records' | 'governance' | 'geo' | 'sources' | 'capabilities' | 'datasets';

export interface PublicOverlayChange {
  county?: string;
  source?: string;
  field: string;
  value: unknown;
  previous: unknown;
}

export interface RainDataMeta {
  source: string;
  server: string;
  dataSource: string;
  database: { name: string; table: string; rows: number; seedLoadedAt: string };
  publicOverlay: PublicOverlayChange[];
  counts: Record<string, number>;
  records: Record<string, number>;
  requestId: string;
  generatedAt: string;
  dbMs: number;
}

export interface RainDataSnapshot {
  meta: RainDataMeta;
  sections: Record<SectionName, Record<string, unknown>>;
}

export interface RainDataProof {
  url: string;
  status: number;
  ms: number;
  bytes: number;
  source: string | null;
  requestId: string | null;
  server: string | null;
  dataSource: string | null;
  serverTiming: string | null;
  sha256Header: string | null;
  sha256Computed: string | null;
  verified: boolean | null;
  loadedAt: string;
  meta: RainDataMeta;
  keysRead: string[];
}

let snapshot: RainDataSnapshot | null = null;
let proof: RainDataProof | null = null;
const keysRead = new Set<string>();

export class BackendDataError extends Error {
  constructor(message: string, readonly url: string, readonly status?: number) {
    super(message);
    this.name = 'BackendDataError';
  }
}

/** Where the data comes from: the same backend base the conversation uses. */
export function dataBase(): string {
  const env = import.meta.env as Record<string, string | undefined>;
  return (env.VITE_RAIN_DATA_BASE || env.VITE_ULTRA_API_BASE || '/api/v3/ui').replace(/\/$/, '');
}

async function sha256Hex(text: string): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null; // not a secure context (plain http on a LAN address)
  const digest = await subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Fetch the whole UI data set from the backend. Call once, before the app renders. */
export async function loadRainData(clientId = 'rain', fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis), timeoutMs = 15_000): Promise<RainDataProof> {
  const url = `${dataBase()}/data?clientId=${encodeURIComponent(clientId)}`;
  const t0 = performance.now();
  // A backend that never answers is reported, not waited on forever.
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetchImpl(url, { cache: 'no-store', headers: { Accept: 'application/json' }, signal: abort.signal });
  } catch (err) {
    throw new BackendDataError(abort.signal.aborted ? `The backend did not answer within ${timeoutMs / 1000} s` : `The backend did not answer: ${(err as Error).message}`, url);
  } finally {
    clearTimeout(timer);
  }
  const text = await res.text();
  if (!res.ok) {
    // A proxy error page is HTML: report its title ("502 Bad Gateway"), not the markup.
    const detail = /^\s*</.test(text) ? (/<title>([^<]*)<\/title>/i.exec(text)?.[1] ?? res.statusText) : text.slice(0, 200);
    throw new BackendDataError(`The backend answered ${res.status}: ${detail}`, url, res.status);
  }
  const body = JSON.parse(text) as RainDataSnapshot;
  const h = (name: string) => res.headers.get(name);
  const computed = await sha256Hex(text);
  const header = h('X-RAIN-Data-Sha256');
  snapshot = body;
  proof = {
    url: new URL(url, globalThis.location?.href ?? 'http://localhost/').href,
    status: res.status,
    ms: Math.round(performance.now() - t0),
    bytes: new TextEncoder().encode(text).length,
    source: h('X-RAIN-Source'),
    requestId: h('X-RAIN-Request-Id'),
    server: h('X-RAIN-Server'),
    dataSource: h('X-RAIN-Data-Source'),
    serverTiming: h('Server-Timing'),
    sha256Header: header,
    sha256Computed: computed,
    verified: computed && header ? computed === header : null,
    // The server's own clock (HTTP Date header): when the backend answered.
    loadedAt: h('Date') ?? body.meta?.generatedAt ?? '',
    meta: body.meta,
    keysRead: [],
  };
  logProof(proof, body);
  return proof;
}

/** Tests and node scripts: hydrate from a snapshot the backend serves (its seed file). */
export function hydrateRainData(data: RainDataSnapshot | { sections: RainDataSnapshot['sections'] }, origin = 'test') {
  snapshot = { meta: { source: origin } as RainDataMeta, ...data } as RainDataSnapshot;
  proof = null;
}

export function isRainDataLoaded() {
  return snapshot !== null;
}

/** One section of the backend data. Throws if the backend has not delivered it. */
export function rainSection<T = unknown>(section: SectionName): Record<string, T> {
  if (!snapshot) {
    throw new BackendDataError(`RAIN data "${section}" was requested before it was loaded from the backend`, `${dataBase()}/data`);
  }
  const sec = snapshot.sections[section];
  if (!sec) throw new BackendDataError(`The backend response has no "${section}" section`, `${dataBase()}/data`);
  return sec as Record<string, T>;
}

/** One value of the backend data, e.g. rainValue('constants', 'COUNTIES'). */
export function rainValue<T>(section: SectionName, key: string): T {
  const value = rainSection(section)[key];
  if (value === undefined) throw new BackendDataError(`The backend data has no ${section}.${key}`, `${dataBase()}/data`);
  keysRead.add(`${section}.${key}`);
  if (proof) proof.keysRead = [...keysRead];
  return tracked(`${section}.${key}`, value) as T;
}

// ─── Which backend data each page shows (console, per page) ─────────────────
//
// Every value handed out above is wrapped so that reading it while a page renders
// is noted. Once per page and dataset, the console says which backend API and
// which datasets the page on screen is built from. Reads during module import
// (before the first render) are not attributed to any page.

const LIVE: Record<string, string> = {
  'constants.COUNTIES': 'county public fields live from rain_v3.public_data',
  'sources.PUBLIC_SOURCES': 'record counts live from rain_v3.public_data',
};
const proxies = new WeakMap<object, object>();
const pageSeen = new Map<string, Set<string>>();
let pending = new Set<string>();
let flushQueued = false;
let pageLog = false;

function tracked(id: string, value: unknown): unknown {
  if (!value || typeof value !== 'object' || import.meta.env.MODE === 'test') return value;
  const cached = proxies.get(value as object);
  if (cached) return cached;
  const proxy = new Proxy(value as object, {
    get(target, prop, receiver) {
      noteRead(id);
      return Reflect.get(target, prop, receiver);
    },
  });
  proxies.set(value as object, proxy);
  return proxy;
}

function pageKey(): string {
  const loc = globalThis.location;
  if (!loc) return '(no page)';
  const u = new URL(loc.href);
  u.searchParams.delete('access');
  return `${u.pathname}${u.search}`;
}

function noteRead(id: string) {
  if (!pageLog) return;
  pending.add(id);
  if (!flushQueued) {
    flushQueued = true;
    queueMicrotask(flushReads);
  }
}

function flushReads() {
  flushQueued = false;
  const page = pageKey();
  const seen = pageSeen.get(page) ?? new Set<string>();
  const fresh = [...pending].filter((k) => !seen.has(k)).sort();
  pending = new Set();
  if (!fresh.length) return;
  fresh.forEach((k) => seen.add(k));
  pageSeen.set(page, seen);
  const datasets = fresh.map((k) => (LIVE[k] ? `${k} [${LIVE[k]}]` : k)).join(', ');
  log.log(
    `%cRAIN%c page ${page} ← backend GET ${proof?.url ?? `${dataBase()}/data`} (request ${proof?.requestId ?? '–'}, ${proof?.dataSource ?? 'backend'}): ${datasets}`,
    PROOF_STYLE.badge,
    '',
  );
}

/** Start attributing data reads to the page on screen (call just before the first render). */
export function enablePageDataLog() {
  pageLog = true;
}

/** Every page seen so far and the backend datasets it read (also on window.__RAIN_PAGE_DATA__). */
export function pageDataLog(): Record<string, string[]> {
  return Object.fromEntries([...pageSeen].map(([page, keys]) => [page, [...keys].sort()]));
}

// ─── Each persona's backend queries (synthetic and public data) ─────────────

interface QuerySummary {
  id: string;
  persona: string;
  data: 'synthetic' | 'public';
  question: string;
  url: string;
}

/** The backend's persona query API, next to the UI API: /api/v3/queries. */
export function queriesBase(): string {
  const env = import.meta.env as Record<string, string | undefined>;
  return (env.VITE_RAIN_QUERIES_BASE || dataBase().replace(/\/ui$/, '/queries')).replace(/\/$/, '');
}

async function getJson(url: string) {
  const t0 = performance.now();
  const res = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json' } });
  logBackendCall('GET', url, res, Math.round(performance.now() - t0));
  if (!res.ok) throw new BackendDataError(`The backend answered ${res.status}`, url, res.status);
  return res.json();
}

const announced = new Set<string>();

/** When a persona opens: list its backend queries in the console (one API call, logged). */
export async function announcePersonaQueries(personaId: string) {
  if (announced.has(personaId) || typeof window === 'undefined' || import.meta.env.MODE === 'test') return;
  announced.add(personaId);
  try {
    const body = (await getJson(`${queriesBase()}?persona=${encodeURIComponent(personaId)}`)) as { count: number; queries: QuerySummary[] };
    const syn = body.queries.filter((q) => q.data === 'synthetic').length;
    log.group(
      `%cRAIN%c ${personaId}: ${body.count} backend queries (${syn} synthetic data, ${body.count - syn} public data). Run one with rainQuery('${body.queries[0]?.id ?? ''}')`,
      PROOF_STYLE.badge,
      PROOF_STYLE.bold,
    );
    log.table(body.queries.map((q) => ({ id: q.id, data: q.data, question: q.question, api: `GET ${q.url}` })));
    log.end();
  } catch {
    // A convenience listing: the UI's data does not depend on it.
  }
}

/** Run one persona query on the backend and print its rows: rainQuery('CMO-P1'). */
export async function rainQuery(id: string) {
  const body = await getJson(`${queriesBase()}/${encodeURIComponent(id)}`);
  log.group(`%cRAIN%c query ${body.id} (${body.persona}, ${body.data} data): ${body.rowCount} rows from ${body.schema} in ${body.ms} ms`, PROOF_STYLE.badge, PROOF_STYLE.bold);
  log.log(body.question);
  log.log(body.sql);
  log.table((body.rows as unknown[]).slice(0, 50));
  log.end();
  return body;
}

/** List the backend's persona queries: rainQueries() or rainQueries('rain_cmo'). */
export async function rainQueries(personaId?: string) {
  const body = await getJson(personaId ? `${queriesBase()}?persona=${encodeURIComponent(personaId)}` : queriesBase());
  log.table((body.queries as QuerySummary[]).map((q) => ({ id: q.id, persona: q.persona, data: q.data, question: q.question, api: `GET ${q.url}` })));
  return body;
}

/** Console helpers: rainQuery(id), rainQueries(persona?), window.__RAIN_PAGE_DATA__. */
export function installConsoleHelpers() {
  const g = globalThis as unknown as Record<string, unknown>;
  g.rainQuery = rainQuery;
  g.rainQueries = rainQueries;
  Object.defineProperty(g, '__RAIN_PAGE_DATA__', { get: pageDataLog, configurable: true });
}


export function rainDataProof(): RainDataProof | null {
  return proof;
}

// ─── Console proof (through core/log, the app's only console) ───────────────

function countOf(v: unknown): number | string {
  if (Array.isArray(v)) return v.length;
  if (v && typeof v === 'object') return `${Object.keys(v).length} fields`;
  return 1;
}

function logProof(p: RainDataProof, body: RainDataSnapshot) {
  const g = globalThis as unknown as { __RAIN_DATA_PROOF__?: RainDataProof };
  g.__RAIN_DATA_PROOF__ = p;
  const m = body.meta;
  log.group(`%cRAIN%c Data loaded from the backend: ${m.database.rows} datasets, ${(p.bytes / 1024).toFixed(0)} KB in ${p.ms} ms`, PROOF_STYLE.badge, PROOF_STYLE.bold);
  log.log(`GET ${p.url} → ${p.status} at ${p.loadedAt} (server clock)`);
  log.log(`X-RAIN-Source: ${p.source} · X-RAIN-Server: ${p.server} · X-RAIN-Request-Id: ${p.requestId} · Server-Timing: ${p.serverTiming}`);
  log.log(`Data source: ${p.dataSource} (database ${m.database.name}, table ${m.database.table}, ${m.database.rows} rows, seed loaded ${m.database.seedLoadedAt})`);
  if (p.verified === null) {
    log.log('%cSHA-256 not compared%c (crypto.subtle needs https or localhost)', PROOF_STYLE.bad, '');
  } else {
    log.log(`%cSHA-256 ${p.verified ? 'verified' : 'MISMATCH'}%c server ${p.sha256Header} · browser ${p.sha256Computed}`, p.verified ? PROOF_STYLE.ok : PROOF_STYLE.bad, '');
  }
  const rows = Object.entries(body.sections).flatMap(([section, entries]) =>
    Object.entries(entries).map(([key, value]) => ({ section, key, items: countOf(value) })));
  log.log(`Every value the UI renders comes from these ${rows.length} backend datasets:`);
  log.table(rows);
  if (m.publicOverlay?.length) {
    log.log(`Public figures computed live by the backend from rain_v3.public_data (${m.publicOverlay.length} values):`);
    log.table(m.publicOverlay.map((o) => ({ where: o.county ?? o.source, field: o.field, value: o.value, replaced: o.previous })));
  }
  log.log('Full proof object: window.__RAIN_DATA_PROOF__');
  log.end();
}
