/**
 * Console proof that a response came from the backend: one line per API call,
 * with the backend's proof headers (X-RAIN-Source, X-RAIN-Server,
 * X-RAIN-Request-Id, X-RAIN-Data-Source, X-RAIN-Turn) and the server's own
 * clock (HTTP Date). Calls are also kept on `window.__RAIN_API_CALLS__`.
 */
import { PROOF_STYLE, proof } from '../log';

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
}

export function logBackendCall(method: string, url: string, res: Response, ms: number): BackendCallRecord {
  const h = (name: string) => res.headers.get(name);
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
  };
  const g = globalThis as unknown as { __RAIN_API_CALLS__?: BackendCallRecord[] };
  (g.__RAIN_API_CALLS__ ??= []).push(rec);
  proof.log(
    `%cRAIN%c ${method} ${url} → ${rec.status} in ${ms} ms · from backend: X-RAIN-Source ${rec.source ?? '–'} · server ${rec.server ?? '–'} · request ${rec.requestId ?? '–'} · data ${rec.dataSource ?? '–'}${rec.turn ? ` · turn ${rec.turn}` : ''}`,
    PROOF_STYLE.badge,
    '',
  );
  return rec;
}
