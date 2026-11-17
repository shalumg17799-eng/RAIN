/**
 * Component identity, variant and alias — the zod-free half of the contract.
 *
 * Every component an answer can draw is named by a **type** (its identity:
 * `trend_chart`, `ussfcu.liquidity_reconciliation`) and a **version**. A type
 * may have **variants**: named presentation forms of the same component,
 * selected by its props (`compact: true`, `kind: 'bar'`). A variant never
 * changes the props schema or the implementation — a different shape is a new
 * type (standard rule 1) — so `(type, variant)` always resolves to the same
 * renderer and the same contract for every client.
 *
 * A retired type id stays drawable as an **alias** of the type that replaced
 * it, so stored conversations, recorded fixtures and API consumers that still
 * send the old id keep rendering. Aliases are declared once, in the market
 * registry (`src/markets/aliases.ts`), and resolved where data enters: the API
 * boundary (`guardComponents`) and the catalog renderer. Recorded answers use
 * live ids only, so the startup bundle never carries the table.
 *
 * The schemas (zod) live in the lazy half: `./contracts` and `./registry`.
 * This file stays dependency-free so the renderer can import it cheaply.
 */
import { getTypeAliases } from '../runtime/contracts';

/** A named presentation form of one type, chosen by its props. */
export interface VariantDef {
  /** Generic and formal (`compact`, `bar`), never a client or persona (rule 2). */
  name: string;
  /** What it looks like and when to send it. */
  description: string;
  /**
   * The prop values that select it, all of which must match. Omitted for the
   * default variant: the one drawn when no other variant's `when` matches.
   */
  when?: Record<string, string | number | boolean | null>;
}

/**
 * The variant a props payload selects: the first variant whose `when` matches,
 * else the default (the variant without `when`), else `undefined` for a type
 * that declares no variants.
 */
export function resolveVariant(variants: VariantDef[] | undefined, props: Record<string, unknown> | undefined): string | undefined {
  if (!variants?.length) return undefined;
  const p = props ?? {};
  const hit = variants.find((v) => v.when && Object.entries(v.when).every(([k, want]) => (p[k] ?? null) === want));
  return (hit ?? variants.find((v) => !v.when))?.name;
}

/**
 * A spec that names its variant (`{ type, variant, props }`): the props with
 * that variant's selecting values applied, or the reason it cannot be drawn —
 * a variant the type does not declare, or props that contradict it. A spec
 * without `variant` passes through unchanged (its props select the variant).
 */
export function applyVariant(variants: VariantDef[] | undefined, variant: string | undefined, props: Record<string, unknown>): { props: Record<string, unknown>; issue?: string } {
  if (!variant) return { props };
  const v = variants?.find((x) => x.name === variant);
  if (!v) return { props, issue: `variant "${variant}" is not one of ${variants?.length ? variants.map((x) => `"${x.name}"`).join(', ') : 'the type\'s (it declares none)'}` };
  if (!v.when) {
    // The default variant: no other variant's selector may be set.
    const other = variants!.find((x) => x.when && Object.entries(x.when).every(([k, want]) => props[k] === want));
    return other ? { props, issue: `variant "${variant}" contradicts props that select "${other.name}"` } : { props };
  }
  const clash = Object.entries(v.when).find(([k, want]) => k in props && props[k] !== want);
  if (clash) return { props, issue: `variant "${variant}" needs ${clash[0]}=${JSON.stringify(clash[1])}, props have ${JSON.stringify(props[clash[0]])}` };
  return { props: { ...props, ...v.when } };
}

/** The type an id resolves to: itself, or the type a retired id is an alias of. */
export function canonicalType(type: string): string {
  return getTypeAliases()[type] ?? type;
}

/**
 * The internal spec a malformed component is replaced with at the data
 * boundary (`guardComponents`), so the renderer draws an "invalid data" notice
 * in its place. Never sent by a backend; not a catalog type.
 */
export const CONTRACT_ERROR_TYPE = '__contract_error__';

export interface ContractErrorProps {
  /** The type the payload named. */
  of: string;
  /** Why it was rejected, one line per problem. */
  issues: string[];
}
