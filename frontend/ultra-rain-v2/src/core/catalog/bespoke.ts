/**
 * Tier 4: a tenant's own components, drawn from `{ type, props }` like any
 * catalog type (the Oct 21 contract, "when no component fits", step 4).
 *
 * A bespoke type has two halves:
 *  • its **contract** — identity, version, title, description, props schema,
 *    variants, defaults, implementation — in the owning client's
 *    `contracts.ts` (core/catalog/contracts.ts), the one canonical entry;
 *  • its **binding** — `bespoke({ type, component })` in each persona's
 *    `manifest.catalog` that draws it, which puts the component in that
 *    persona's chunk so the chat can draw it synchronously.
 * `contracts.test.ts` holds the two together: every binding has a contract,
 * every binding of a type is the same component, and that component is the
 * one the contract's `implementation` names.
 *
 * A persona's `answers()` returns specs naming these types, so every chat
 * answer — catalog or bespoke — is contract data the backend can send, and one
 * renderer draws it. Each bespoke type is a candidate to promote into the
 * catalog (tiers 2–3) or retire.
 *
 * Zod-free on purpose: persona chunks import this, and the schema library stays
 * in the lazy catalog chunk.
 */
import type { ComponentType } from 'react';
import type { CatalogActions } from './types';
import type { ContractSpec } from '../contract/spec';

export interface BespokeEntry {
  /** `<tenant>.<snake_name>` — namespaced, so it never collides with a catalog type. */
  type: string;
  version: number;
  tier: 4;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<any>;
  /**
   * A wrapper the chat column needs around this card: a spacing class, or
   * `true` for a plain block. It lives here, with the frontend, never in the
   * props (standard rule 6).
   */
  frame?: string | true;
  /** Contract props → the component's props (e.g. a chip callback). */
  adapt?: (props: Record<string, unknown>, actions: CatalogActions) => Record<string, unknown>;
  /**
   * @deprecated Identity metadata — title, description, why no catalog type
   * fits, tenants — lives in the type's contract (`<client>/contracts.ts`),
   * the one place the catalog export, the API and the docs read it from. A
   * binding carries only what the renderer needs. Kept optional so a
   * declaration written before the contracts still type-checks.
   */
  title?: string;
  /** @deprecated See `title`. */
  description?: string;
  /** @deprecated See `title`. */
  whyNotCatalog?: string;
  /** @deprecated See `title`. */
  tenants?: string[];
}

/** Bind a bespoke type to its component for one persona. `version` defaults to 1. */
export function bespoke(e: Omit<BespokeEntry, 'tier' | 'version'> & { version?: number }): BespokeEntry {
  return { version: 1, ...e, tier: 4 };
}

/** One component spec, as `POST /ask` returns it in `components[]`. */
export function spec(type: string, props: Record<string, unknown> = {}, version = 1, variant?: string): ContractSpec {
  return variant ? { type, version, variant, props } : { type, version, props };
}
