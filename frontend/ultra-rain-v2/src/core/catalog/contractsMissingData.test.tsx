/**
 * Missing data: what a contract allows to be absent, the component survives.
 *
 * For every bespoke contract, the recorded example is drawn twice more, the
 * way the chat draws it (inside the persona's provider stack) — and every
 * catalog type's example is drawn with its optional fields removed:
 *  • with every optional top-level field removed — a payload the contract
 *    accepts must not crash the card;
 *  • with every collection the contract lets be empty emptied (top level and
 *    one level down) — an empty list must not crash the card either.
 * A collection a component cannot draw empty is declared `.min(1)` in its
 * contract, so the API boundary turns such a payload into the invalid-data
 * notice instead of a broken card.
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { z } from 'zod';
import { getMarkets } from '../runtime/registry';
import { getContractNamespaces } from '../runtime/contracts';
import { contractComponents, type ContractSpec } from '../contract/spec';
import { listBespokeContracts, type BespokeContract } from './contracts';
import { bespokeElement } from './resolve';
import { indexBespoke, BespokeContext } from './bespokeContext';
import type { BespokeEntry } from './bespoke';
import { CATALOG } from './registry';
import { PersonaHarness } from '@/test/harness';
import { settleLazy } from '@/test/eagerLazy';

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react')>();
  const { createEagerLazy } = await import('@/test/eagerLazy');
  return { ...actual, lazy: createEagerLazy(actual.createElement) };
});
vi.mock('react-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-dom')>();
  return { ...actual, createPortal: (children: unknown) => children };
});

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});
afterAll(() => vi.restoreAllMocks());

interface Case { contract: BespokeContract; client: string; persona: string; binding: BespokeEntry; spec: ContractSpec }
const cases: Case[] = [];

beforeAll(async () => {
  const contracts = new Map<string, BespokeContract>();
  for (const ns of getContractNamespaces()) for (const c of await listBespokeContracts(ns)) contracts.set(c.type, c);
  for (const market of getMarkets()) for (const client of market.clients) for (const persona of client.personas) {
    const m = (await persona.load()).default;
    for (const c of contracts.values()) {
      if (c.example.persona !== persona.id) continue;
      const flow = m.flows.chatFlows[c.example.flowKey] as { ui_components_to_render?: unknown[] } | undefined;
      const ui = flow?.ui_components_to_render ?? [];
      const specs = [...contractComponents(ui), ...(m.answers?.({ flowKey: c.example.flowKey, role: 'ai', uiComponents: ui }, m.signals ?? []) ?? [])];
      const spec = specs.find((s) => s.type === c.type);
      const binding = (m.catalog ?? []).find((e) => e.type === c.type);
      if (spec && binding) cases.push({ contract: c, client: client.id, persona: persona.id, binding, spec });
    }
  }
  await settleLazy();
}, 120_000);

const unwrap = (t: z.ZodType): z.ZodType => {
  let x = t;
  while (x instanceof z.ZodOptional || x instanceof z.ZodNullable || x instanceof z.ZodDefault) x = (x as unknown as { unwrap: () => z.ZodType }).unwrap();
  return x;
};
const isOptional = (t: z.ZodType) => t.safeParse(undefined).success;
/** Whether the schema lets this collection be empty. */
const allowsEmpty = (t: z.ZodType) => unwrap(t).safeParse([]).success;

function draw(c: Case, props: Record<string, unknown>): string | null {
  try {
    const el = bespokeElement({ ...c.spec, props }, indexBespoke([c.binding]));
    renderToStaticMarkup(
      <PersonaHarness clientId={c.client} personaId={c.persona}>
        <BespokeContext.Provider value={indexBespoke([c.binding])}>{el}</BespokeContext.Provider>
      </PersonaHarness>,
    );
    return null;
  } catch (err) {
    return String((err as Error)?.message ?? err).split('\n')[0].slice(0, 120);
  }
}

/** The example with every collection the schema allows empty, emptied (two levels). */
function emptied(schema: z.ZodType, value: unknown, depth = 0): unknown {
  const s = unwrap(schema);
  if (Array.isArray(value)) return allowsEmpty(schema) ? [] : value;
  if (depth < 2 && s instanceof z.ZodObject && value && typeof value === 'object') {
    const shape = s.shape as Record<string, z.ZodType>;
    return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, shape[k] ? emptied(shape[k], v, depth + 1) : v]));
  }
  return value;
}

describe('bespoke components survive the data their contracts allow to be missing', () => {
  it('every contract has a recorded example to test with', () => {
    // The floor only guards against the collection silently finding nothing.
    expect(cases.length).toBeGreaterThanOrEqual(10);
  });

  it('the recorded example itself draws', () => {
    const failures = cases.map((c) => [c.contract.type, draw(c, c.spec.props)] as const).filter(([, e]) => e);
    expect(failures).toEqual([]);
  });

  it('with every optional top-level field removed', () => {
    const failures: string[] = [];
    for (const c of cases) {
      if (!(c.contract.schema instanceof z.ZodObject)) continue;
      const shape = c.contract.schema.shape as Record<string, z.ZodType>;
      const props = Object.fromEntries(Object.entries(c.spec.props).filter(([k]) => k === 'children' || !shape[k] || !isOptional(shape[k])));
      if (Object.keys(props).length === Object.keys(c.spec.props).length) continue;
      expect(c.contract.schema.safeParse(props).success, `${c.contract.type}: the stripped payload is still valid`).toBe(true);
      const err = draw(c, props);
      if (err) failures.push(`${c.contract.type}: ${err}`);
    }
    expect(failures).toEqual([]);
  });

  it('with every collection it allows to be empty emptied', () => {
    const failures: string[] = [];
    for (const c of cases) {
      const props = emptied(c.contract.schema, c.spec.props) as Record<string, unknown>;
      if (JSON.stringify(props) === JSON.stringify(c.spec.props)) continue;
      expect(c.contract.schema.safeParse(props).success, `${c.contract.type}: the emptied payload is still valid`).toBe(true);
      const err = draw(c, props);
      if (err) failures.push(`${c.contract.type}: ${err}`);
    }
    expect(failures).toEqual([]);
  });

  it('catalog types draw their example with every optional field removed', async () => {
    const failures: string[] = [];
    for (const e of CATALOG) {
      if (!(e.schema instanceof z.ZodObject)) continue;
      const shape = e.schema.shape as Record<string, z.ZodType>;
      const example = e.example as Record<string, unknown>;
      const props = Object.fromEntries(Object.entries(example).filter(([k]) => !shape[k] || !isOptional(shape[k])));
      const parsed = e.schema.safeParse(props);
      if (!parsed.success) { failures.push(`${e.type}: stripped example fails its own schema`); continue; }
      const Comp = (await e.load()).default;
      const drawn = e.adapt ? e.adapt(parsed.data as Record<string, unknown>, {}) : (parsed.data as Record<string, unknown>);
      try {
        renderToStaticMarkup(<PersonaHarness clientId="rain" personaId="rain_ceo"><Comp {...drawn} /></PersonaHarness>);
      } catch (err) {
        failures.push(`${e.type}: ${String((err as Error)?.message ?? err).split('\n')[0].slice(0, 120)}`);
      }
    }
    expect(failures).toEqual([]);
  }, 60_000);
});
