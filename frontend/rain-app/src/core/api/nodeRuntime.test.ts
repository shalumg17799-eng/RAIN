// @vitest-environment node
/**
 * The reference API (`npm run mock-api`) runs in Node, with no `document` or
 * `window`. Every persona must load there and answer every endpoint, or the
 * backend team gets an error where the UI shows a turn. Two ways that broke
 * before: a manifest statically importing a browser-only library (NFCU's graph
 * and mermaid cards are now behind lazy boundaries), and a persona with no
 * `__default__` turn, so an unmatched question had no answer.
 */
import { describe, it, expect } from 'vitest';
import { getMarkets } from '../runtime/registry';
import { createRecordedApi } from './recorded';

const api = createRecordedApi();
const entries = getMarkets().flatMap((m) => m.clients.flatMap((c) => c.personas.map((p) => ({ clientId: c.id, personaId: p.id }))));

describe('every persona answers the API in Node', () => {
  it.each(entries.map((e) => [`${e.clientId}/${e.personaId}`, e] as const))('%s', async (_label, ref) => {
    const context = await api.getContext(ref);
    expect(context.persona.id).toBe(ref.personaId);
    const briefing = await api.getBriefing(ref);
    expect(briefing.chips.length).toBeGreaterThan(0);
    const first = await api.ask({ ...ref, input: briefing.chips[0] });
    expect(first.text.length).toBeGreaterThan(0);
    const offScript = await api.ask({ ...ref, input: 'what is the weather on mars' });
    expect(offScript.text.length).toBeGreaterThan(0);
  }, 30_000);
});
