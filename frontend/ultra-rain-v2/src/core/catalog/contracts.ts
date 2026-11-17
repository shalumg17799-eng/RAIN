/**
 * Component contracts — the one lookup from a type id to the data it takes.
 *
 * Tiers 2–3 (catalog) carry their contract on the registry entry
 * (`./registry`). Tier 4 (a tenant's bespoke types) carry it in the owning
 * client's `contracts.ts`, one entry per type, loaded on demand through the
 * market registry (`src/markets/contracts.ts`). Both answer the same question
 * through `getContract(type)`: identity, version, tier, the props schema, its
 * variants, where the implementation lives and, for bespoke types, the
 * defaults the component applies when an optional field is missing.
 *
 * `guardComponents` is the data boundary: it validates a turn's components
 * against their contracts and swaps a malformed one for a notice, so data from
 * an API (or a hand-edited fixture) can never draw a broken card. Recorded
 * answers are held to the same contracts by `contracts.test.ts`.
 *
 * Zod lives here, in the lazy half (see `./contract` for the zod-free half).
 */
import { z } from 'zod';
import { getContractModule } from '../runtime/contracts';
import type { ContractSpec } from '../contract/spec';
import { CATALOG, getCatalogEntry } from './registry';
import { canonicalType, resolveVariant, applyVariant, CONTRACT_ERROR_TYPE, type VariantDef, type ContractErrorProps } from './contract';

/** A bespoke (tier 4) type's contract, declared in its client's `contracts.ts`. */
export interface BespokeContract {
  /** `<namespace>.<snake_name>`: the identity answers and the API send. */
  type: string;
  version: number;
  title: string;
  /** When to use it, in one sentence (what an LLM would read). */
  description: string;
  /** Why no catalog type fits (the gap ladder); required for new types. */
  whyNotCatalog?: string;
  /** Clients whose answers draw it. */
  tenants: string[];
  /** The module the component is in (`@/components/…`), checked against the binding. */
  implementation: string;
  /** The props schema. Objects are open: extra fields are allowed and ignored. */
  schema: z.ZodType;
  variants?: VariantDef[];
  /** What the component uses when an optional field is missing. */
  defaults?: Record<string, unknown>;
  /** A recorded turn that draws it — its example payload, read at export time. */
  example: { persona: string; flowKey: string };
}

/** Declare a client's contracts (identity is checked for uniqueness by the contract test). */
export function defineContracts(list: BespokeContract[]): BespokeContract[] {
  return list;
}

/** Any type's contract, catalog or bespoke, in one shape. */
export interface ResolvedContract {
  type: string;
  version: number;
  tier: 2 | 3 | 4;
  title: string;
  description: string;
  schema: z.ZodType;
  variants?: VariantDef[];
  implementation?: string;
  defaults?: Record<string, unknown>;
}

const loaded = new Map<string, Promise<Map<string, BespokeContract>>>();

/** A bespoke namespace's contracts, loaded once. */
function namespaceContracts(ns: string): Promise<Map<string, BespokeContract>> {
  if (!loaded.has(ns)) {
    const load = getContractModule(ns);
    loaded.set(ns, load ? load().then((m) => new Map(m.default.map((c) => [c.type, c]))) : Promise.resolve(new Map()));
  }
  return loaded.get(ns)!;
}

/** The contract for a type id (aliases resolved), or `undefined` for an unknown type. */
export async function getContract(type: string): Promise<ResolvedContract | undefined> {
  const id = canonicalType(type);
  const entry = getCatalogEntry(id);
  if (entry) {
    return { type: entry.type, version: entry.version, tier: entry.tier as 2 | 3, title: entry.title, description: entry.description, schema: entry.schema, variants: entry.variants };
  }
  const dot = id.indexOf('.');
  if (dot < 1) return undefined;
  const c = (await namespaceContracts(id.slice(0, dot))).get(id);
  return c && { type: c.type, version: c.version, tier: 4, title: c.title, description: c.description, schema: c.schema, variants: c.variants, implementation: c.implementation, defaults: c.defaults };
}

/** Every bespoke contract of a namespace (tests, the exporter). */
export async function listBespokeContracts(ns: string): Promise<BespokeContract[]> {
  return [...(await namespaceContracts(ns)).values()];
}

export interface SpecCheck {
  ok: boolean;
  /** The type it resolved to (an alias resolves to its replacement). */
  type: string;
  /** Set when the spec named a retired id. */
  aliasOf?: string;
  tier?: 2 | 3 | 4;
  variant?: string;
  /** Empty when `ok`. */
  issues: string[];
}

const issueLines = (e: z.ZodError) => e.issues.slice(0, 5).map((i) => `${i.path.join('.') || '(props)'}: ${i.message}`);

/** Check one spec (not its children) against its contract. */
export async function checkSpec(spec: ContractSpec): Promise<SpecCheck> {
  const type = canonicalType(spec.type);
  const aliasOf = type !== spec.type ? spec.type : undefined;
  const c = await getContract(type);
  if (!c) return { ok: false, type, aliasOf, issues: [`unknown component type "${spec.type}"`] };
  const issues: string[] = [];
  if ((spec.version ?? 1) > c.version) issues.push(`version ${spec.version} is newer than the contract's ${c.version}`);
  // A named variant applies its selecting props (or is rejected).
  const applied = applyVariant(c.variants, spec.variant, spec.props ?? {});
  if (applied.issue) issues.push(applied.issue);
  const { children: _children, ...props } = applied.props;
  // Tier 3 layout blocks validate their children separately; tier 4 schemas never list `children`.
  const parsed = c.schema.safeParse(c.tier === 4 ? props : applied.props);
  if (!parsed.success) issues.push(...issueLines(parsed.error));
  return { ok: issues.length === 0, type, aliasOf, tier: c.tier, variant: spec.variant ?? resolveVariant(c.variants, props), issues };
}

const isSpec = (v: unknown): v is ContractSpec => !!v && typeof v === 'object' && typeof (v as ContractSpec).type === 'string' && typeof (v as ContractSpec).props === 'object';

/**
 * The data boundary for components from outside the app (the API): resolves
 * aliases, applies a named variant's selecting props, validates each component
 * and its nested children against their contracts, and replaces a malformed
 * one (or an unsupported variant) with a notice spec. Unknown types
 * pass through unchanged — the renderer skips them, as it always has.
 */
export async function guardComponents(specs: ContractSpec[] | undefined): Promise<ContractSpec[]> {
  return Promise.all((specs ?? []).map(async (spec) => {
    if (!isSpec(spec)) return spec;
    const check = await checkSpec(spec);
    if (!check.tier) return spec;
    if (!check.ok) {
      const props: ContractErrorProps = { of: check.type, issues: check.issues };
      return { type: CONTRACT_ERROR_TYPE, version: 1, props: props as unknown as Record<string, unknown> };
    }
    const c = await getContract(check.type);
    const props = applyVariant(c?.variants, spec.variant, spec.props ?? {}).props;
    const kids = props.children;
    const children = Array.isArray(kids) ? await guardComponents(kids.filter(isSpec)) : isSpec(kids) ? (await guardComponents([kids]))[0] : kids;
    return { ...spec, type: check.type, props: kids === undefined ? props : { ...props, children } };
  }));
}

/** Catalog (tier 2–3) types, for listings that want every identity. */
export const catalogTypes = (): string[] => CATALOG.map((e) => e.type);
