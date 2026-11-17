/**
 * The render net — every chat card of every persona, fingerprinted.
 *
 * For each registered persona and each of its scripted turns, this builds the
 * AI message the workspace would build, asks the persona's `answers` for the
 * components it draws under that turn (catalog and bespoke types alike), renders each card to static HTML
 * inside the real provider stack, and records a short hash of the markup.
 *
 * The standardization refactor moves data out of components and merges
 * duplicates. Those changes must not change a single rendered byte, and this
 * snapshot is how that is proven: a changed hash names the persona, the turn
 * and the card. Update the snapshot (`vitest -u`) only for an intended change.
 *
 * Cards that throw during render are recorded as `!error` — the snapshot then
 * holds the pre-existing failures too, so a new one cannot slip in unnoticed.
 *
 * Components a turn declares in contract form (`{ type, props }`) are drawn the
 * way the catalog renderer draws them — schema-parsed, adapted, same component
 * — and fingerprinted under the same component name. So when a card moves from
 * a persona's switchboard into its flow data, an unchanged hash is the proof
 * that the move changed nothing on screen.
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { createHash } from 'node:crypto';
import { renderToStaticMarkup } from 'react-dom/server';
import { getMarkets } from './registry';
import { PersonaHarness } from '@/test/harness';
import { settleLazy } from '@/test/eagerLazy';
import { contractComponents } from '../contract/spec';
import { getCatalogEntry } from '../catalog/registry';
import { BespokeContext, indexBespoke } from '../catalog/bespokeContext';
import { bespokeElement } from '../catalog/resolve';

// The server renderer cannot draw portals; render a modal's content in place so
// confirm dialogs are fingerprinted like every other card.
// Lazy boundaries resolve before anything is drawn (see test/eagerLazy.js), so
// a fingerprint never depends on how fast a dynamic import loaded.
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  const { createEagerLazy } = await import('@/test/eagerLazy');
  return { ...actual, lazy: createEagerLazy(actual.createElement) };
});
vi.mock('react-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, createPortal: (children) => children };
});

const FIXED_NOW = new Date('2026-10-14T13:30:00Z');

/** Deterministic Math.random so animated/jittered cards render the same bytes. */
function seededRandom(seed = 42) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

const entries = getMarkets().flatMap((market) =>
  market.clients.flatMap((client) => client.personas.map((persona) => ({ client, persona }))),
);

const nameOf = (el) => {
  const t = el.type;
  if (typeof t === 'string') return t;
  return t?.displayName || t?.name || (t?.$$typeof ? String(t.$$typeof.description || 'memo') : 'anonymous');
};

const hash = (s) => createHash('sha1').update(s).digest('hex').slice(0, 10);

describe('persona chat cards render identically', () => {
  let restoreRandom;
  beforeAll(() => {
    vi.useFakeTimers({ now: FIXED_NOW, toFake: ['Date'] });
    const rand = seededRandom();
    const spy = vi.spyOn(Math, 'random').mockImplementation(rand);
    restoreRandom = () => spy.mockRestore();
    // Card renders that warn (keys, act) are not what this net is for.
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterAll(() => {
    restoreRandom?.();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it.each(entries.map((e) => [`${e.client.id}/${e.persona.id}`, e]))(
    '%s',
    async (_label, { client, persona }) => {
      const manifest = (await persona.load()).default;
      await settleLazy();
      const fingerprint = {};
      const bespoke = indexBespoke(manifest.catalog);
      const draw = (el) => {
        try {
          const html = renderToStaticMarkup(
            <PersonaHarness clientId={client.id} personaId={persona.id}>
              <BespokeContext.Provider value={bespoke}>{el}</BespokeContext.Provider>
            </PersonaHarness>,
          );
          return `${nameOf(el)}#${hash(html)}`;
        } catch (err) {
          return `${nameOf(el)}!error ${String(err?.message || err).split('\n')[0].slice(0, 80)}`;
        }
      };
      // A spec is drawn the way the chat draws it: the persona's own (bespoke)
      // types directly, catalog types schema-parsed and adapted.
      const drawSpec = async (spec) => {
        const own = bespokeElement(spec, bespoke);
        if (own) return draw(own);
        const entry = getCatalogEntry(spec.type);
        if (!entry) return `!unknown-type ${spec.type}`;
        const parsed = entry.schema.safeParse(spec.props);
        if (!parsed.success) return `!invalid-props ${spec.type}`;
        const Comp = (await entry.load()).default;
        const props = entry.adapt ? entry.adapt(parsed.data, {}) : parsed.data;
        return draw(<Comp {...props} />);
      };
      for (const [flowKey, flow] of Object.entries(manifest.flows.chatFlows)) {
        const specs = contractComponents(flow.ui_components_to_render);
        if (!specs.length) continue;
        const drawn = [];
        for (const spec of specs) drawn.push(await drawSpec(spec));
        fingerprint[flowKey] = drawn;
      }
      if (typeof manifest.answers === 'function') {
        for (const [flowKey, flow] of Object.entries(manifest.flows.chatFlows)) {
          const msg = {
            id: `msg-${flowKey}`,
            role: 'ai',
            flowKey,
            text: flow.ai_message || flow.ai_response || '',
            sources: flow.data_sources_used || [],
            uiComponents: flow.ui_components_to_render || [],
            confidence: flow.confidence,
            capability: flow.capability,
          };
          let specs;
          try {
            specs = manifest.answers(msg, manifest.signals);
          } catch (err) {
            fingerprint[flowKey] = [`!switch-error ${String(err?.message || err).slice(0, 80)}`];
            continue;
          }
          if (!specs?.length) continue;
          const drawn = [];
          for (const spec of specs) drawn.push(await drawSpec(spec));
          // Same order as the workspace: flow-declared specs, then the answer.
          fingerprint[flowKey] = [...(fingerprint[flowKey] || []), ...drawn];
        }
      }
      expect(fingerprint).toMatchSnapshot();
    },
    60_000,
  );
});
