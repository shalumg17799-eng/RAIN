/**
 * The API seam. The recorded adapter must answer every endpoint for every
 * persona in the contract shape — it is both how demos run without a backend
 * and the reference the backend is tested against. The HTTP adapter must send
 * the documented requests and reject a turn that breaks the contract.
 */
import { describe, it, expect, vi } from 'vitest';
import { createRecordedApi, ApiError } from './recorded';
import { createHttpApi } from './http';
import { aiTurnSchema } from '../contract/aiTurn';
import { signalSchema } from '../contract/signal';
import { getMarkets } from '../runtime/registry';
import type { PersonaManifest } from '../types';

const api = createRecordedApi();
const entries = getMarkets().flatMap((m) => m.clients.flatMap((c) => c.personas.map((p) => ({ clientId: c.id, persona: p }))));

describe('recorded adapter', () => {
  it.each(entries.map((e) => [`${e.clientId}/${e.persona.id}`, e] as const))('%s answers every endpoint in the contract shape', async (_l, { clientId, persona }) => {
    const ref = { clientId, personaId: persona.id };
    const manifest = (await persona.load()).default as PersonaManifest;

    const ctx = await api.getContext(ref);
    expect(ctx.client.id).toBe(clientId);
    expect(ctx.persona.id).toBe(persona.id);
    expect(ctx.personas.map((p) => p.id)).toContain(persona.id);

    const brief = await api.getBriefing(ref);
    expect(aiTurnSchema.safeParse(brief.greeting).success).toBe(true);
    // The greeting the chat opens on: the persona's rewrite of its greeting key, if any.
    const rewritten = manifest.flows.resolveFlowKey?.(manifest.ui.greetingFlowKey);
    expect(brief.greeting.id).toBe(rewritten && manifest.flows.chatFlows[rewritten] ? rewritten : manifest.ui.greetingFlowKey);
    for (const s of brief.signals) expect(signalSchema.safeParse(s).success, s.id).toBe(true);
    expect(brief.kpis).toHaveLength(manifest.ui.stats.length);
    expect(brief.chips).toEqual(manifest.ui.initialChips);

    // Every starter chip gets a contract-shaped answer.
    for (const chip of manifest.ui.initialChips) {
      const turn = await api.ask({ ...ref, input: chip });
      expect(aiTurnSchema.safeParse(turn).success, chip).toBe(true);
    }

    // Every wired action confirms.
    for (const actionId of Object.keys(manifest.flows.actionConfirmMap ?? {})) {
      const { turn } = await api.runAction({ ...ref, actionId });
      expect(aiTurnSchema.safeParse(turn).success).toBe(true);
    }
  }, 20_000);

  it('rejects an unknown persona with a 404', async () => {
    await expect(api.getContext({ clientId: 'nfcu', personaId: 'nobody' })).rejects.toMatchObject({ status: 404 });
    await expect(api.getContext({ clientId: 'nfcu', personaId: 'nobody' })).rejects.toBeInstanceOf(ApiError);
  });

  it('answers a chip with the same turn the scripted engine picks', async () => {
    const ref = { clientId: 'rain', personaId: 'rain_ceo' };
    const manifest = (await getMarkets().flatMap((m) => m.clients).find((c) => c.id === 'rain')!.personas.find((p) => p.id === 'rain_ceo')!.load()).default as PersonaManifest;
    const [chip, flowKey] = Object.entries(manifest.flows.chipToFlowKey).find(([, k]) => k in manifest.flows.chatFlows)!;
    const turn = await api.ask({ ...ref, input: chip });
    expect(turn.id).toBe(flowKey);
  });

  it('builds the TTS URL the narration hooks use', () => {
    expect(api.ttsUrl({ slide: 's1', tenant: 'esfcu' })).toBe('/api/tts?slide=s1&tenant=esfcu');
  });
});

describe('http adapter', () => {
  const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  const turn = { id: 't1', text: 'Hello', citations: [], components: [{ type: 'text', version: 1, props: { text: 'x' } }], chips: ['Next'] };

  it('posts an ask and validates the turn', async () => {
    const fetchMock = vi.fn(() => ok(turn));
    const http = createHttpApi('https://api.example.test/v1/', fetchMock as unknown as typeof fetch);
    const res = await http.ask({ clientId: 'nfcu', personaId: 'nfcu_supervisor', input: 'Hi' });
    expect(res.id).toBe('t1');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://api.example.test/v1/ask');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({ clientId: 'nfcu', personaId: 'nfcu_supervisor', input: 'Hi' });
  });

  it('sends context and briefing as GET with the persona in the query', async () => {
    const fetchMock = vi.fn((url: string) => ok(url.includes('/briefing') ? { greeting: turn, signals: [], kpis: [], chips: [] } : {}));
    const http = createHttpApi('https://api.example.test', fetchMock as unknown as typeof fetch);
    await http.getBriefing({ clientId: 'esfcu', personaId: 'esfcu_ceo' });
    expect(fetchMock.mock.calls[0][0]).toBe('https://api.example.test/briefing?clientId=esfcu&personaId=esfcu_ceo');
  });

  it('rejects a turn that breaks the contract, and a failed status', async () => {
    const bad = createHttpApi('https://x.test', (() => ok({ text: 'no id' })) as unknown as typeof fetch);
    await expect(bad.ask({ clientId: 'a', personaId: 'b', input: 'c' })).rejects.toThrow();
    const down = createHttpApi('https://x.test', (() => Promise.resolve(new Response('', { status: 503 }))) as unknown as typeof fetch);
    await expect(down.ask({ clientId: 'a', personaId: 'b', input: 'c' })).rejects.toMatchObject({ status: 503 });
  });
});
