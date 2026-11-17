/**
 * The HTTP adapter: the same six endpoints, served by the backend.
 *
 * Selected with `VITE_ULTRA_API_MODE=http` and `VITE_ULTRA_API_BASE`. Every
 * AI turn is validated against the `AiTurn` schema on arrival, so a payload
 * that drifts from the contract fails loudly here rather than as a blank card.
 * Each component in it is then checked against its own contract
 * (`guardComponents`): a retired type id resolves to its replacement, and a
 * component whose props do not match draws an "invalid data" notice in its
 * place while the rest of the turn renders.
 */
import { aiTurnSchema, type AiTurn } from '../contract/aiTurn';
import { guardComponents } from '../catalog/contracts';
import { ApiError } from './recorded';
import { logBackendCall, logBackendFailure } from './proof';
import type { ActionResponse, BriefingResponse, ContextResponse, UltraApi } from './types';

export function createHttpApi(base: string, fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)): UltraApi {
  const root = base.replace(/\/$/, '');
  async function call<T>(method: 'GET' | 'POST', path: string, body?: unknown, query?: Record<string, string>): Promise<T> {
    const qs = query ? `?${new URLSearchParams(query).toString()}` : '';
    const t0 = performance.now();
    let res: Response;
    try {
      res = await fetchImpl(`${root}${path}${qs}`, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      logBackendFailure(method, `${root}${path}${qs}`, err, Math.round(performance.now() - t0), body);
      throw err;
    }
    // The console shows every backend call: method, path, status, time, and the backend's proof headers.
    if (res.headers) logBackendCall(method, `${root}${path}${qs}`, res, Math.round(performance.now() - t0), body);
    if (!res.ok) throw new ApiError(res.status, `${method} ${path} → ${res.status}`);
    return (await res.json()) as T;
  }
  /** The envelope, then every component against its contract. */
  async function turn(raw: unknown): Promise<AiTurn> {
    const t = aiTurnSchema.parse(raw);
    return { ...t, components: (await guardComponents(t.components)) as AiTurn['components'] };
  }
  return {
    getContext: (ref) => call<ContextResponse>('GET', '/context', undefined, { ...ref }),
    async getBriefing(ref) {
      const b = await call<BriefingResponse>('GET', '/briefing', undefined, { ...ref });
      return { ...b, greeting: await turn(b.greeting) };
    },
    async ask(req) {
      return turn(await call('POST', '/ask', req));
    },
    async runAction(req) {
      const r = await call<ActionResponse>('POST', `/actions/${encodeURIComponent(req.actionId)}`, { clientId: req.clientId, personaId: req.personaId });
      return { turn: await turn(r.turn) };
    },
    getCatalog: () => call('GET', '/catalog'),
    ttsUrl({ slide, tenant, persona }) {
      const q = new URLSearchParams({ slide });
      if (tenant) q.set('tenant', tenant);
      if (persona) q.set('persona', persona);
      return `${root}/tts?${q.toString()}`;
    },
  };
}
