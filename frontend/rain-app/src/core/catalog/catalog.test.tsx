/**
 * Catalog contract tests — what the backend relies on.
 *
 *  • every entry is well-formed (snake_case type, version, a description the
 *    LLM can read, a tier);
 *  • every example validates against its own schema and renders;
 *  • every schema exports to JSON Schema (that is what `GET /catalog` serves);
 *  • every persona's every scripted turn reads into the `AiTurn` contract.
 */
import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { z } from 'zod';
import { MemoryRouter } from 'react-router-dom';
import { CATALOG, getCatalogEntry } from './registry';
import ComponentRenderer from './ComponentRenderer';
import { aiTurnSchema, toAiTurn, contractComponents } from '../contract/aiTurn';
import { getMarkets } from '../runtime/registry';
import type { ChatFlow } from '../types';

// Recharts' ResponsiveContainer needs a measurable box in jsdom.
beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});
afterAll(() => vi.restoreAllMocks());

describe('catalog entries', () => {
  it('has unique snake_case types with a description, version and tier', () => {
    const types = CATALOG.map((e) => e.type);
    expect(new Set(types).size).toBe(types.length);
    for (const e of CATALOG) {
      expect(e.type, e.type).toMatch(/^[a-z][a-z0-9_]*$/);
      expect(e.version).toBeGreaterThanOrEqual(1);
      expect([1, 2, 3, 4]).toContain(e.tier);
      expect(e.description.length, `${e.type} needs a usable description`).toBeGreaterThan(30);
    }
  });

  it.each(CATALOG.map((e) => [e.type, e] as const))('%s example satisfies its schema', (_t, e) => {
    const r = e.schema.safeParse(e.example);
    expect(r.success, r.success ? '' : JSON.stringify(r.error.issues)).toBe(true);
  });

  it.each(CATALOG.map((e) => [e.type, e] as const))('%s exports to JSON Schema', (_t, e) => {
    const json = z.toJSONSchema(e.schema, { unrepresentable: 'any' });
    expect(json).toHaveProperty('type', 'object');
  });

  it.each(CATALOG.map((e) => [e.type, e] as const))('%s renders its example through the renderer', async (type, e) => {
    const { container } = render(
      <MemoryRouter>
        <ComponentRenderer components={[{ type, version: e.version, props: e.example as Record<string, unknown> }]} />
      </MemoryRouter>,
    );
    await waitFor(() => expect(container.querySelector('[aria-hidden="true"].animate-pulse')).toBeNull(), { timeout: 5000 });
    // Text or graphics (a sparkline is SVG only).
    expect(container.querySelector('svg, p, span, div, table, figure'), `${type} rendered nothing`).not.toBeNull();
    expect(screen.queryByText(/couldn.t be rendered/i)).toBeNull();
    expect(screen.queryByText(/didn.t match the catalog/i)).toBeNull();
  });
});

describe('renderer safety', () => {
  it('skips an unknown type and flags invalid props without throwing', async () => {
    render(
      <ComponentRenderer components={[
        { type: 'no_such_component', version: 1, props: {} },
        { type: 'target_bar', version: 1, props: { value: 'not a number' } },
      ]} />,
    );
    expect(await screen.findByText(/didn.t match the catalog/i)).toBeInTheDocument();
  });

  it('draws nested compose children', async () => {
    render(
      <ComponentRenderer components={[{ type: 'grid', version: 1, props: { columns: 2, children: [
        { type: 'stat', version: 1, props: { label: 'Alpha', value: '1' } },
        { type: 'stat', version: 1, props: { label: 'Beta', value: '2' } },
      ] } }]} />,
    );
    expect(await screen.findByText('Alpha')).toBeInTheDocument();
    expect(await screen.findByText('Beta')).toBeInTheDocument();
  });
});

describe('recorded responses', () => {
  const entries = getMarkets().flatMap((m) => m.clients.flatMap((c) => c.personas.map((p) => ({ c, p }))));

  it.each(entries.map((e) => [`${e.c.id}/${e.p.id}`, e] as const))('%s: every turn reads into the AiTurn contract', async (_l, { p }) => {
    const manifest = (await p.load()).default;
    for (const [key, flow] of Object.entries(manifest.flows.chatFlows)) {
      const turn = toAiTurn(key, flow as ChatFlow);
      const r = aiTurnSchema.safeParse(turn);
      expect(r.success, `${key}: ${r.success ? '' : JSON.stringify(r.error.issues)}`).toBe(true);
      // Any component written in contract form must name a catalog type and satisfy it.
      for (const spec of contractComponents((flow as ChatFlow).ui_components_to_render)) {
        const entry = getCatalogEntry(spec.type);
        expect(entry, `${key}: unknown catalog type "${spec.type}"`).toBeDefined();
        expect(entry!.schema.safeParse(spec.props).success, `${key}: ${spec.type} props invalid`).toBe(true);
      }
    }
  }, 20_000);
});
