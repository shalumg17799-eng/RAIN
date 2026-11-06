/**
 * The HTTP adapter: the same six endpoints, served by the backend.
 *
 * Selected with `VITE_ULTRA_API_MODE=http` and `VITE_ULTRA_API_BASE`. Every
 * AI turn is validated against the `AiTurn` schema on arrival, so a payload
 * that drifts from the contract fails loudly here rather than as a blank card.
 */
import { aiTurnSchema } from '../contract/aiTurn';
import { ApiError } from './recorded';
import type { ActionResponse, BriefingResponse, ContextResponse, UltraApi } from './types';

export function createHttpApi(base: string, fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)): UltraApi {
  const root = base.replace(/\/$/, '');
  async function call<T>(method: 'GET' | 'POST', path: string, body?: unknown, query?: Record<string, string>): Promise<T> {
    const qs = query ? `?${new URLSearchParams(query).toString()}` : '';
    const res = await fetchImpl(`${root}${path}${qs}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new ApiError(res.status, `${method} ${path} → ${res.status}`);
    return (await res.json()) as T;
  }
  return {
    getContext: (ref) => call<ContextResponse>('GET', '/context', undefined, { ...ref }),
    async getBriefing(ref) {
      const b = await call<BriefingResponse>('GET', '/briefing', undefined, { ...ref });
      return { ...b, greeting: aiTurnSchema.parse(b.greeting) };
    },
    async ask(req) {
      return aiTurnSchema.parse(await call('POST', '/ask', req));
    },
    async runAction(req) {
      const r = await call<ActionResponse>('POST', `/actions/${encodeURIComponent(req.actionId)}`, { clientId: req.clientId, personaId: req.personaId });
      return { turn: aiTurnSchema.parse(r.turn) };
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
