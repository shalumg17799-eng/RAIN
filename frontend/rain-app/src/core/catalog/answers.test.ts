/**
 * Every persona's recorded answers are contract data (the Oct 21 contract).
 *
 * For every turn of every persona, the components `answers()` returns must be
 * what a backend could send: a known type (catalog, or the persona's own
 * bespoke entry), props that pass the catalog schema, and nothing a JSON
 * response cannot carry — no functions, no React elements. And every bespoke
 * type a persona declares is drawn by at least one of its turns.
 */
import { describe, it, expect } from 'vitest';
import { getMarkets } from '../runtime/registry';
import { getCatalogEntry } from './registry';
import type { ContractSpec } from '../contract/spec';

const entries = getMarkets().flatMap((m) => m.clients.flatMap((c) => c.personas.map((p) => ({ client: c, persona: p }))));

/** The first non-JSON value in `v`, as a path, or null. */
function nonJson(v: unknown, path = 'props'): string | null {
  if (v === null || ['string', 'number', 'boolean'].includes(typeof v)) return null;
  if (typeof v === 'undefined') return null;
  if (typeof v === 'function') return `${path} is a function`;
  if (typeof v === 'object' && v && '$$typeof' in v) return `${path} is a React element`;
  if (Array.isArray(v)) { for (let i = 0; i < v.length; i++) { const r = nonJson(v[i], `${path}[${i}]`); if (r) return r; } return null; }
  if (typeof v === 'object') { for (const [k, x] of Object.entries(v as object)) { const r = nonJson(x, `${path}.${k}`); if (r) return r; } return null; }
  return `${path} is a ${typeof v}`;
}

/** Specs plus every spec nested under `props.children`. */
function flatten(specs: ContractSpec[]): ContractSpec[] {
  return specs.flatMap((s) => {
    const kids = Array.isArray(s.props?.children) ? (s.props.children as ContractSpec[]).filter((c) => c && typeof c === 'object' && 'type' in c) : [];
    return [s, ...flatten(kids)];
  });
}

describe('recorded answers are contract data', () => {
  it.each(entries.map((e) => [`${e.client.id}/${e.persona.id}`, e] as const))('%s', async (_label, { persona }) => {
    const m = (await persona.load()).default;
    const own = new Map((m.catalog ?? []).map((e) => [e.type, e]));
    expect(own.size, 'a bespoke type is declared twice').toBe((m.catalog ?? []).length);
    for (const e of m.catalog ?? []) {
      expect(e.type, 'bespoke types are namespaced <tenant>.<name>').toMatch(/^[a-z_]+\.[a-z0-9_]+$/);
      expect(e.description.length, `${e.type} needs a description`).toBeGreaterThan(10);
      if (e.whyNotCatalog !== undefined) expect(e.whyNotCatalog.length, `${e.type}: whyNotCatalog should name the closest catalog type and why it does not fit`).toBeGreaterThan(30);
    }
    const drawn = new Set<string>();
    for (const [flowKey, flow] of Object.entries(m.flows.chatFlows)) {
      const msg = { flowKey, role: 'ai', uiComponents: (flow as { ui_components_to_render?: unknown[] }).ui_components_to_render ?? [] };
      const specs = m.answers?.(msg, m.signals ?? []) ?? [];
      for (const s of flatten(specs)) {
        drawn.add(s.type);
        expect(nonJson(s.props), `${flowKey}: ${s.type}`).toBeNull();
        if (own.has(s.type)) continue;
        const entry = getCatalogEntry(s.type);
        expect(entry, `${flowKey}: unknown type ${s.type}`).toBeDefined();
        const parsed = entry!.schema.safeParse(s.props);
        expect(parsed.success, `${flowKey}: ${s.type} props do not match the catalog schema`).toBe(true);
      }
    }
    for (const type of own.keys()) expect(drawn.has(type), `${type} is declared but no turn draws it`).toBe(true);
  }, 60_000);
});
