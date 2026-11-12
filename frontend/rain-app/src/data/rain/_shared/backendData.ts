/**
 * The RAIN UI's only data source: the backend.
 *
 * Every number, record, dataset, map shape, source and persona contract the UI
 * shows is fetched once at boot from `GET {VITE_ULTRA_API_BASE}/data?clientId=rain`
 * (rain-api `ui_data_v4.py`: Postgres `rain_v4.ui_v4.dataset`, with the county
 * public figures computed live from `rain_v4.public_data`). Nothing is bundled:
 * the data modules in this folder read from here, and reading before the
 * backend has answered throws instead of falling back to anything local.
 *
 * The browser console shows the backend API calls only (core/api/proof.ts). The
 * load's proof (the backend's proof headers, the SHA-256 of the body as sent by the
 * server against the one computed here) is kept on `window.__RAIN_DATA_PROOF__`.
 */

import { logBackendCall, logBackendFailure } from '@core/api/proof';

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
  /** Numbers are computed from `computedFrom` schemas per request; `configTable` holds templates and config only. */
  database: { name: string; computedFrom?: string[]; configTable?: string; configRows?: number; configLoadedAt?: string };
  computed?: { computed: { computed: boolean; ms: number; version: number; ageSeconds: number }; asOf: string; periodEnd: string } | null;
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
  return (env.VITE_RAIN_DATA_BASE || env.VITE_ULTRA_API_BASE || '/api/v4/ui').replace(/\/$/, '');
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
    const message = abort.signal.aborted ? `The backend did not answer within ${timeoutMs / 1000} s` : `The backend did not answer: ${(err as Error).message}`;
    logBackendFailure('GET', url, message, Math.round(performance.now() - t0));
    throw new BackendDataError(message, url);
  } finally {
    clearTimeout(timer);
  }
  logBackendCall('GET', url, res, Math.round(performance.now() - t0));
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
  keepProof(proof);
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

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v);
const rowKey = (v: unknown) => (isObj(v) ? (v.id ?? v.memberId) : undefined);

/** Update `target` to equal `source` without replacing it, so every module holding it sees the new values. */
function mergeInPlace(target: unknown, source: unknown) {
  if (Array.isArray(target) && Array.isArray(source)) {
    // Rows keep their identity when their id matches (a selected member stays the same object).
    const byId = new Map(target.filter(isObj).map((x) => [rowKey(x), x] as const));
    const next = source.map((s) => {
      const t = rowKey(s) !== undefined ? byId.get(rowKey(s)) : undefined;
      if (t && isObj(s)) {
        mergeInPlace(t, s);
        return t;
      }
      return s;
    });
    target.splice(0, target.length, ...next);
    return;
  }
  if (!isObj(target) || !isObj(source)) return;
  for (const k of Object.keys(target)) if (!(k in source)) delete target[k];
  for (const [k, v] of Object.entries(source)) {
    const t = target[k];
    if (t && v && typeof t === 'object' && typeof v === 'object' && Array.isArray(t) === Array.isArray(v)) mergeInPlace(t, v);
    else target[k] = v;
  }
}

/**
 * Re-read the backend data after a write-back (flowApi) and update every loaded value in place: the
 * backend recomputes the numbers from the changed rows, and modules that already hold a value (CARE,
 * LINDA, the campaign members...) see the new state without a page reload.
 */
export async function refreshRainData(clientId = 'rain'): Promise<boolean> {
  if (!snapshot) return false;
  const url = `${dataBase()}/data?clientId=${encodeURIComponent(clientId)}`;
  const t0 = performance.now();
  const res = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json' } });
  logBackendCall('GET', url, res, Math.round(performance.now() - t0));
  if (!res.ok) return false;
  const body = (await res.json()) as RainDataSnapshot;
  const sections = snapshot.sections as Record<string, Record<string, unknown>>;
  for (const [name, sec] of Object.entries(body.sections)) {
    if (sections[name]) mergeInPlace(sections[name], sec);
    else sections[name] = sec;
  }
  snapshot.meta = body.meta;
  if (proof) proof.meta = body.meta;
  return true;
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

// ─── Which backend data each page shows (window.__RAIN_PAGE_DATA__) ─────────
//
// Every value handed out above is wrapped so that reading it while a page renders
// is noted per page (not printed: the console shows backend API calls only).
// Reads during module import (before the first render) are not attributed to any page.

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

/** The backend's persona query API, next to the UI API: /api/v4/queries. */
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

/** Run one persona query on the backend and return its result: await rainQuery('CMO-P1'). */
export async function rainQuery(id: string) {
  return getJson(`${queriesBase()}/${encodeURIComponent(id)}`);
}

/** List the backend's persona queries: await rainQueries() or rainQueries('rain_cmo'). */
export async function rainQueries(personaId?: string): Promise<{ count: number; queries: QuerySummary[] }> {
  return getJson(personaId ? `${queriesBase()}?persona=${encodeURIComponent(personaId)}` : queriesBase());
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

// ─── Proof of the boot load (kept on window, not printed) ───────────────────

function keepProof(p: RainDataProof) {
  const g = globalThis as unknown as { __RAIN_DATA_PROOF__?: RainDataProof };
  g.__RAIN_DATA_PROOF__ = p;
}
