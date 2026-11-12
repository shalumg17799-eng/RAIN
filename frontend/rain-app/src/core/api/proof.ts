/**
 * The browser console's only content: every backend API call, one collapsed entry each.
 *
 *   API  GET /api/v4/ui/data?clientId=rain → 200 · 812 ms
 *   API  POST /api/v4/ui/ask → 200 · 884 ms · turn query:CEO-S1
 *   API  POST /api/v4/flow/book → 200 · 140 ms
 *
 * Expand an entry for the backend's proof headers (X-RAIN-Request-Id, X-RAIN-Server,
 * X-RAIN-Source, X-RAIN-Data-Source, X-RAIN-Turn, Server-Timing), the server's clock
 * (HTTP Date) and, for a POST, what was sent. Calls are also kept on
 * `window.__RAIN_API_CALLS__`.
 */
import { apiConsole } from '../log';

export interface BackendCallRecord {
  method: string;
  url: string;
  status: number;
  ms: number;
  source: string | null;
  server: string | null;
  requestId: string | null;
  dataSource: string | null;
  turn: string | null;
  serverDate: string | null;
  serverTiming?: string | null;
  error?: string;
}

const STYLE = {
  badge: 'background:#0b3d91;color:#fff;padding:1px 6px;border-radius:3px;font-weight:600',
  plain: '',
  ok: 'color:#1a7f37;font-weight:600',
  bad: 'color:#cf222e;font-weight:600',
  muted: 'color:#6b7280',
};

function shortPath(url: string): string {
  try {
    const u = new URL(url, globalThis.location?.href ?? 'http://localhost/');
    return `${u.pathname}${u.search}`;
  } catch {
    return url;
  }
}

function absolute(url: string): string {
  try {
    return new URL(url, globalThis.location?.href ?? 'http://localhost/').href;
  } catch {
    return url;
  }
}

function keep(rec: BackendCallRecord) {
  const g = globalThis as unknown as { __RAIN_API_CALLS__?: BackendCallRecord[] };
  (g.__RAIN_API_CALLS__ ??= []).push(rec);
}

/** Log one backend call that answered (any status). `sent` is the request body of a POST. */
export function logBackendCall(method: string, url: string, res: Response, ms: number, sent?: unknown): BackendCallRecord {
  const h = (name: string) => res.headers?.get(name) ?? null;
  const rec: BackendCallRecord = {
    method,
    url,
    status: res.status,
    ms,
    source: h('X-RAIN-Source'),
    server: h('X-RAIN-Server'),
    requestId: h('X-RAIN-Request-Id'),
    dataSource: h('X-RAIN-Data-Source'),
    turn: h('X-RAIN-Turn'),
    serverDate: h('Date'),
    serverTiming: h('Server-Timing'),
  };
  keep(rec);
  apiConsole.call(
    `%cAPI%c ${method} ${shortPath(url)} → %c${res.status}%c · ${ms} ms${rec.turn ? ` · turn ${rec.turn}` : ''}`,
    [STYLE.badge, STYLE.plain, res.ok ? STYLE.ok : STYLE.bad, STYLE.muted],
    {
      url: absolute(url),
      status: res.status,
      time: `${ms} ms`,
      requestId: rec.requestId,
      server: rec.server,
      source: rec.source,
      dataSource: rec.dataSource,
      serverTiming: rec.serverTiming,
      ...(rec.turn ? { turn: rec.turn } : {}),
      serverDate: rec.serverDate,
      ...(sent !== undefined ? { sent } : {}),
    },
  );
  return rec;
}

/** Log one backend call that got no answer (network error, timeout). */
export function logBackendFailure(method: string, url: string, error: unknown, ms: number, sent?: unknown): BackendCallRecord {
  const message = error instanceof Error ? error.message : String(error);
  const rec: BackendCallRecord = {
    method, url, status: 0, ms, source: null, server: null, requestId: null, dataSource: null, turn: null, serverDate: null, error: message,
  };
  keep(rec);
  apiConsole.call(
    `%cAPI%c ${method} ${shortPath(url)} → %cno response%c · ${ms} ms`,
    [STYLE.badge, STYLE.plain, STYLE.bad, STYLE.muted],
    { url: absolute(url), error: message, time: `${ms} ms`, ...(sent !== undefined ? { sent } : {}) },
  );
  return rec;
}
