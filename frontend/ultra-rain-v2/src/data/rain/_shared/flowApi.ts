/**
 * The write-back flow: what a persona does in a workbench is written to the backend
 * (POST /api/v4/flow/<action>, rain-api flow_v4.py → rows in rain_v4.synthetic), then
 * the UI data is re-read so every number the next screen shows is computed from the
 * changed rows. Each write shows in the browser console as a backend API call (core/api/proof.ts).
 *
 * The demo store (components/value-based-care/shell/store.ts) still updates at once (optimistic);
 * the backend keeps the change, so another persona, another browser or a reload sees it.
 */
import { logBackendCall, logBackendFailure } from '@core/api/proof';
import { dataBase, refreshRainData } from './backendData';

export type FlowAction = 'handoff' | 'contact' | 'book' | 'reply' | 'reading' | 'signoff' | 'note' | 'reset';

export interface FlowResult {
  ok: boolean;
  flow: string;
  event?: number;
  at?: string;
  result?: Record<string, unknown>;
}

/** The backend's write-back API, next to the UI API: /api/v4/flow. */
export function flowBase(): string {
  const env = import.meta.env as Record<string, string | undefined>;
  return (env.VITE_RAIN_FLOW_BASE || dataBase().replace(/\/ui2?$/, '/flow')).replace(/\/$/, '');
}

const listeners = new Set<(r: FlowResult) => void>();
/** Called after every successful write-back, once the UI data has been re-read. */
export function onFlow(fn: (r: FlowResult) => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** Write one action to the backend; resolves to null when it could not be written (the UI keeps working). */
export async function postFlow(action: FlowAction, body: Record<string, unknown> = {}): Promise<FlowResult | null> {
  if (import.meta.env.MODE === 'test' || typeof fetch !== 'function') return null;
  const url = `${flowBase()}/${action}`;
  const t0 = performance.now();
  let res: Response;
  try {
    res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body) });
  } catch (err) {
    logBackendFailure('POST', url, err, Math.round(performance.now() - t0), body);
    return null;
  }
  logBackendCall('POST', url, res, Math.round(performance.now() - t0), body);
  const json = (await res.json().catch(() => null)) as FlowResult | { detail?: string } | null;
  if (!res.ok || !json || !('ok' in json)) return null;
  try {
    await refreshRainData();
  } catch {
    // the write is kept; the next data load shows it
  }
  listeners.forEach((l) => l(json));
  return json;
}
