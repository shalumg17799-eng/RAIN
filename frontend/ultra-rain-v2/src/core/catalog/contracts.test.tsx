/**
 * Component contracts: every identity resolves to one contract and one
 * renderer, and every recorded answer satisfies its contract.
 *
 *  • Registry — each bespoke namespace that personas bind has a contracts
 *    module; each contract is well-formed, unique and namespaced; every
 *    binding has a contract and every contract a binding; every binding of a
 *    type is the same component, and it is the one the contract names.
 *  • Data — every recorded answer of every persona validates against the
 *    contract of its type (catalog or bespoke), and each contract's example
 *    pointer names a turn that draws it.
 *  • Variants — names unique, one default at most, selectors name real
 *    fields, and each example resolves to a declared variant.
 *  • Compatibility — every alias resolves to a live type and draws it; an
 *    unknown type is reported and skipped; a malformed payload or an
 *    unsupported variant is replaced by the invalid-data notice at the
 *    boundary while the rest of the turn renders.
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { z } from 'zod';
import { getMarkets } from '../runtime/registry';
import { getContractNamespaces, getTypeAliases } from '../runtime/contracts';
import { contractComponents, type ContractSpec } from '../contract/spec';
import { getCatalogEntry, CATALOG } from './registry';
import { checkSpec, getContract, guardComponents, listBespokeContracts, type BespokeContract } from './contracts';
import { resolveVariant, canonicalType, CONTRACT_ERROR_TYPE, type VariantDef } from './contract';
import { bespokeElement } from './resolve';
import { indexBespoke } from './bespokeContext';
import { RenderSpec } from './ComponentRenderer';
import type { BespokeEntry } from './bespoke';

beforeAll(() => {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
});
afterAll(() => vi.restoreAllMocks());

const flatten = (specs: ContractSpec[]): ContractSpec[] => specs.flatMap((sp) => {
  const kids = Array.isArray(sp.props?.children) ? (sp.props.children as unknown[]).filter((c): c is ContractSpec => !!c && typeof c === 'object' && 'type' in (c as object)) : [];
  return [sp, ...flatten(kids)];
});
const nsOf = (t: string) => t.slice(0, t.indexOf('.'));

interface Use { client: string; persona: string; flowKey: string; spec: ContractSpec }
let bindings: Array<{ persona: string; entry: BespokeEntry }> = [];
let uses: Use[] = [];
const contracts = new Map<string, BespokeContract>();

beforeAll(async () => {
  for (const market of getMarkets()) for (const client of market.clients) for (const persona of client.personas) {
    const m = (await persona.load()).default;
    for (const entry of m.catalog ?? []) bindings.push({ persona: persona.id, entry });
    for (const [flowKey, flow] of Object.entries(m.flows.chatFlows)) {
      const ui = (flow as { ui_components_to_render?: unknown[] }).ui_components_to_render ?? [];
      for (const spec of flatten([...contractComponents(ui), ...(m.answers?.({ flowKey, role: 'ai', uiComponents: ui }, m.signals ?? []) ?? [])])) {
        uses.push({ client: client.id, persona: persona.id, flowKey, spec });
      }
    }
  }
  for (const ns of getContractNamespaces()) for (const c of await listBespokeContracts(ns)) contracts.set(c.type, c);
  bindings = bindings.sort((a, b) => a.entry.type.localeCompare(b.entry.type));
  uses = uses.sort((a, b) => a.spec.type.localeCompare(b.spec.type));
}, 120_000);

describe('the registry: one identity, one contract, one renderer', () => {
  it('every namespace personas bind has a contracts module', () => {
    const bound = [...new Set(bindings.map((b) => nsOf(b.entry.type)))].sort();
    const missing = bound.filter((ns) => !getContractNamespaces().includes(ns));
    expect(missing, 'namespaces without contracts (src/markets/contracts.ts)').toEqual([]);
  });

  it('contracts are well-formed, unique and in their own namespace', async () => {
    for (const ns of getContractNamespaces()) {
      const list = await listBespokeContracts(ns);
      expect(list.length, `${ns} declares no contracts`).toBeGreaterThan(0);
      const types = list.map((c) => c.type);
      expect(new Set(types).size, `${ns}: a type is declared twice`).toBe(types.length);
      for (const c of list) {
        expect(c.type, 'namespaced <ns>.<snake_name>').toMatch(/^[a-z_]+\.[a-z0-9_]+$/);
        expect(nsOf(c.type), `${c.type} is in ${ns}'s contracts`).toBe(ns);
        expect(getCatalogEntry(c.type), `${c.type} collides with a catalog type`).toBeUndefined();
        expect(c.version).toBeGreaterThanOrEqual(1);
        expect(c.title.length, `${c.type} needs a title`).toBeGreaterThan(2);
        expect(c.description.length, `${c.type} needs a description`).toBeGreaterThan(10);
        if (c.whyNotCatalog !== undefined) expect(c.whyNotCatalog.length, `${c.type}: whyNotCatalog should name the closest catalog type and why it does not fit`).toBeGreaterThan(30);
        expect(c.tenants.length, `${c.type} names no tenant`).toBeGreaterThan(0);
        expect(c.implementation, `${c.type} names its module`).toMatch(/^@\//);
        expect(c.schema, `${c.type} has a schema`).toBeInstanceOf(z.ZodType);
        expect(() => z.toJSONSchema(c.schema, { unrepresentable: 'any', io: 'input' }), `${c.type} exports to JSON Schema`).not.toThrow();
      }
    }
  });

  it('every binding has a contract and every contract is bound', () => {
    const bound = new Set(bindings.map((b) => b.entry.type));
    expect([...bound].filter((t) => !contracts.has(t)), 'bound without a contract').toEqual([]);
    expect([...contracts.keys()].filter((t) => !bound.has(t)), 'contract without a binding').toEqual([]);
  });

  it('every binding of a type is one component — the one the contract names', async () => {
    const byType = new Map<string, BespokeEntry[]>();
    for (const b of bindings) byType.set(b.entry.type, [...(byType.get(b.entry.type) ?? []), b.entry]);
    for (const [type, list] of byType) {
      expect(new Set(list.map((e) => e.component)).size, `${type} is bound to different components`).toBe(1);
      expect(new Set(list.map((e) => String(e.adapt ?? ''))).size, `${type} is adapted differently per persona`).toBe(1);
      expect(new Set(list.map((e) => String(e.frame ?? ''))).size, `${type} is framed differently per persona`).toBe(1);
      const c = contracts.get(type);
      if (!c) continue;
      const [path, exportName] = c.implementation.split('#');
      const mod = await import(/* @vite-ignore */ path);
      expect(mod[exportName ?? 'default'], `${type}: ${c.implementation} is not the bound component`).toBe(list[0].component);
    }
  }, 120_000);

  it('bindings carry only what the renderer needs (metadata is the contract\'s)', () => {
    const extra = bindings.filter((b) => b.entry.title !== undefined || b.entry.description !== undefined || b.entry.whyNotCatalog !== undefined || b.entry.tenants !== undefined);
    expect(extra.map((b) => `${b.persona}: ${b.entry.type}`)).toEqual([]);
  });

  it('catalog entries declare their variants consistently', () => {
    for (const e of CATALOG) checkVariants(e.type, e.variants, e.schema);
  });
});

/** Variant names unique, one default at most, selectors on real fields. */
function checkVariants(type: string, variants: VariantDef[] | undefined, schema: z.ZodType) {
  if (!variants) return;
  const names = variants.map((v) => v.name);
  expect(new Set(names).size, `${type}: duplicate variant name`).toBe(names.length);
  expect(variants.filter((v) => !v.when).length, `${type}: more than one default variant`).toBeLessThanOrEqual(1);
  const shape = schema instanceof z.ZodObject ? schema.shape : undefined;
  for (const v of variants) {
    expect(v.name, `${type}: variant names are generic snake/kebab words`).toMatch(/^[a-z][a-z0-9_-]*$/);
    expect(v.description.length, `${type}.${v.name} needs a description`).toBeGreaterThan(5);
    for (const k of Object.keys(v.when ?? {})) if (shape) expect(k in shape, `${type}.${v.name} selects on unknown field "${k}"`).toBe(true);
  }
}

describe('recorded answers satisfy their contracts', () => {
  it('every component of every turn of every persona validates', async () => {
    const failures: string[] = [];
    for (const u of uses) {
      const check = await checkSpec(u.spec);
      if (!check.ok) failures.push(`${u.persona} · ${u.flowKey} · ${u.spec.type}: ${check.issues.join('; ')}`);
    }
    expect(failures).toEqual([]);
  }, 120_000);

  it('each contract\'s example names a turn that draws it, and resolves to a declared variant', async () => {
    for (const c of contracts.values()) {
      const u = uses.find((x) => x.persona === c.example.persona && x.flowKey === c.example.flowKey && x.spec.type === c.type);
      expect(u, `${c.type}: example ${c.example.persona}/${c.example.flowKey} does not draw it`).toBeDefined();
      checkVariants(c.type, c.variants, c.schema);
      if (c.variants?.length && u) {
        const v = resolveVariant(c.variants, u.spec.props);
        expect(c.variants.map((x) => x.name), `${c.type}: example resolves to no variant`).toContain(v);
      }
    }
  });

  it('every documented default is a value the schema accepts for that field', () => {
    for (const c of contracts.values()) {
      if (!c.defaults || !(c.schema instanceof z.ZodObject)) continue;
      for (const [k, v] of Object.entries(c.defaults)) {
        const field = c.schema.shape[k] as z.ZodType | undefined;
        expect(field, `${c.type}: default for undocumented field "${k}"`).toBeDefined();
        if (v !== null) expect(field!.safeParse(v).success, `${c.type}: default ${k}=${JSON.stringify(v)} fails its own schema`).toBe(true);
      }
    }
  });
});

describe('compatibility at the boundary', () => {
  it('every alias resolves to a live type that is not itself an alias', async () => {
    for (const [old, now] of Object.entries(getTypeAliases())) {
      expect(old in getTypeAliases() && now in getTypeAliases(), `${old} → ${now} chains`).toBe(false);
      expect(contracts.has(old) || !!getCatalogEntry(old), `${old} is retired but still declared`).toBe(false);
      expect(await getContract(old), `${old} → ${now} resolves to nothing`).toBeDefined();
      expect(canonicalType(old)).toBe(now);
    }
  });

  it('a retired id validates and draws as the type that replaced it', async () => {
    for (const [old, now] of Object.entries(getTypeAliases())) {
      const u = uses.find((x) => x.spec.type === now);
      expect(u, `${now} has a recorded use to test the alias with`).toBeDefined();
      const legacy = { ...u!.spec, type: old };
      const check = await checkSpec(legacy);
      expect(check.ok, `${old}: ${check.issues.join('; ')}`).toBe(true);
      expect(check.aliasOf).toBe(old);
      expect(check.type).toBe(now);
      const [guarded] = await guardComponents([legacy]);
      expect(guarded.type).toBe(now);
      const binding = bindings.find((b) => b.entry.type === now);
      if (binding) {
        const index = indexBespoke([binding.entry]);
        expect(bespokeElement(guarded, index)?.type, `${old} draws ${now}'s component`).toBe(bespokeElement(u!.spec, index)?.type);
      }
    }
  });

  it('recorded answers use live ids only (retired ids are resolved at the boundary)', () => {
    const retired = uses.filter((u) => u.spec.type in getTypeAliases()).map((u) => `${u.persona} · ${u.flowKey} · ${u.spec.type}`);
    expect(retired).toEqual([]);
  });

  it('an unknown type is reported and passed through for the renderer to skip', async () => {
    const spec = { type: 'no_such_component', version: 1, props: {} };
    const check = await checkSpec(spec);
    expect(check.ok).toBe(false);
    expect(check.issues[0]).toMatch(/unknown component type/);
    expect(await guardComponents([spec])).toEqual([spec]);
    const { container } = render(<RenderSpec spec={spec} />);
    expect(container.innerHTML).toBe('');
  });

  it('a malformed payload becomes the invalid-data notice; valid siblings are untouched', async () => {
    const good = { type: 'callout', version: 1, props: { title: 'Fine', status: 'good' } };
    const bad = { type: 'trend_chart', version: 1, props: { points: 'not a list' } };
    const [a, b] = await guardComponents([good, bad]);
    expect(a).toEqual(good);
    expect(b.type).toBe(CONTRACT_ERROR_TYPE);
    expect((b.props as { of: string }).of).toBe('trend_chart');
    render(<RenderSpec spec={b} />);
    expect(screen.getByRole('note').textContent).toMatch(/trend chart couldn.t be shown/);
  });

  it('a malformed bespoke payload is caught the same way', async () => {
    const c = [...contracts.values()].find((x) => x.schema instanceof z.ZodObject && Object.values(x.schema.shape).some((f) => !(f as z.ZodType).safeParse(undefined).success));
    expect(c, 'a bespoke contract with a required field').toBeDefined();
    const [guarded] = await guardComponents([{ type: c!.type, version: 1, props: {} }]);
    expect(guarded.type).toBe(CONTRACT_ERROR_TYPE);
  });

  it('an unsupported variant is rejected, a supported one passes', async () => {
    const chart = { type: 'chart', version: 1, props: { kind: 'bar', series: [{ name: 'A', points: [{ label: 'x', value: 1 }] }] } };
    expect((await checkSpec(chart)).variant).toBe('bar');
    expect((await checkSpec(chart)).ok).toBe(true);
    const odd = { ...chart, props: { ...chart.props, kind: 'pie' } };
    expect((await checkSpec(odd)).ok).toBe(false);
    for (const c of contracts.values()) {
      const shape = c.schema instanceof z.ZodObject ? c.schema.shape : {};
      const enumField = Object.entries(shape).find(([k, f]) => c.variants?.some((v) => v.when && k in v.when) && (f as z.ZodType).safeParse('__unsupported__').success === false && (f as z.ZodType).safeParse(undefined).success);
      if (!enumField) continue;
      const u = uses.find((x) => x.spec.type === c.type)!;
      const r = await checkSpec({ ...u.spec, props: { ...u.spec.props, [enumField[0]]: '__unsupported__' } });
      expect(r.ok, `${c.type}: ${enumField[0]}='__unsupported__' should be rejected`).toBe(false);
    }
  });

  it('a named variant applies its selecting props; an undeclared or contradicted one is rejected', async () => {
    const series = [{ name: 'A', points: [{ label: 'x', value: 1 }] }];
    // `variant` instead of the selecting prop: valid, and the boundary fills the prop in.
    const named = { type: 'chart', version: 1, variant: 'bar', props: { series } };
    expect((await checkSpec(named)).ok).toBe(true);
    expect((await checkSpec(named)).variant).toBe('bar');
    expect((await guardComponents([named]))[0].props).toMatchObject({ kind: 'bar' });
    // A variant the type does not declare.
    const odd = await guardComponents([{ type: 'chart', version: 1, variant: 'pie', props: { series } }]);
    expect(odd[0].type).toBe(CONTRACT_ERROR_TYPE);
    expect((odd[0].props as { issues: string[] }).issues.join()).toMatch(/variant "pie" is not one of/);
    // Props that contradict the named variant.
    const clash = await checkSpec({ type: 'chart', version: 1, variant: 'bar', props: { kind: 'line', series } });
    expect(clash.ok).toBe(false);
    // The default variant cannot be named alongside another variant's selector.
    expect((await checkSpec({ type: 'target_bar', version: 1, variant: 'default', props: { value: 1, compact: true } })).ok).toBe(false);
    expect((await checkSpec({ type: 'target_bar', version: 1, variant: 'compact', props: { value: 1 } })).ok).toBe(true);
    // A bespoke variant through the same path.
    const c = [...contracts.values()].find((x) => x.variants?.some((v) => v.when));
    const v = c!.variants!.find((x) => x.when)!;
    const u = uses.find((x) => x.spec.type === c!.type)!;
    const bare = Object.fromEntries(Object.entries(u.spec.props).filter(([k]) => !(k in v.when!)));
    const [g] = await guardComponents([{ type: c!.type, version: 1, variant: v.name, props: bare }]);
    expect(g.type, `${c!.type} variant ${v.name}`).toBe(c!.type);
    expect(g.props).toMatchObject(v.when!);
  });

  it('a recorded answer that names a variant already carries its selecting props', async () => {
    for (const u of uses.filter((x) => x.spec.variant)) {
      const c = await getContract(u.spec.type);
      const v = c?.variants?.find((x) => x.name === u.spec.variant);
      expect(v, `${u.persona} · ${u.flowKey}: ${u.spec.type} names undeclared variant ${u.spec.variant}`).toBeDefined();
      for (const [k, want] of Object.entries(v?.when ?? {})) expect(u.spec.props[k], `${u.persona} · ${u.flowKey}: ${u.spec.type}.${k}`).toBe(want);
    }
  });

  it('a newer version than the contract is reported', async () => {
    const r = await checkSpec({ type: 'callout', version: 99, props: { title: 'x', status: 'good' } });
    expect(r.ok).toBe(false);
    expect(r.issues.join()).toMatch(/newer/);
  });
});
