/**
 * Tier 4: a tenant's own components, drawn from `{ type, props }` like any
 * catalog type (the Oct 21 contract, "when no component fits", step 4).
 *
 * A persona lists the bespoke types its answers draw in `manifest.catalog`;
 * its `answers()` returns specs naming them. So every chat answer — catalog or
 * bespoke — is contract data the backend can send, and one renderer draws it.
 * Bespoke types are flagged and counted in docs/catalog/catalog.json and the
 * reuse report; each one is a candidate to promote into the catalog (tiers
 * 2–3) or retire.
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
  title: string;
  /** When to use it, in one sentence (what an LLM would read). */
  description: string;
  /**
   * Why no catalog type fits, after trying the gap ladder: which type came
   * closest (pick), why one optional prop would not do (extend), and why the
   * tier-3 blocks cannot compose it. Required for every new bespoke type: the
   * standard audit counts entries without one, and that count may not rise.
   */
  whyNotCatalog?: string;
  /** Clients whose answers draw it. */
  tenants: string[];
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
}

/** Declare a bespoke type. `version` defaults to 1. */
export function bespoke(e: Omit<BespokeEntry, 'tier' | 'version'> & { version?: number }): BespokeEntry {
  return { version: 1, ...e, tier: 4 };
}

/** One component spec, as `POST /ask` returns it in `components[]`. */
export function spec(type: string, props: Record<string, unknown> = {}, version = 1): ContractSpec {
  return { type, version, props };
}
