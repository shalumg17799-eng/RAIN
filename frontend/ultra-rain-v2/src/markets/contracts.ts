/**
 * Where every bespoke (tier 4) component contract lives, and which retired
 * type ids still resolve — the market registry's half of the component
 * contract (core/catalog/contract.ts explains identity, variant and alias).
 *
 * A bespoke type is named `<namespace>.<name>`; its contract is in the
 * namespace's `contracts.ts`, loaded only when something validates or lists
 * it (the API boundary, the contract test, `npm run catalog`), so the schemas
 * never ride in a persona's chunk. Catalog types (tiers 2–3) carry their
 * contracts in core/catalog/registry.ts and need nothing here.
 *
 * Read through core/runtime/contracts (by the lazy validator only, so these
 * loaders stay out of the startup bundle); retired ids are in ./aliases.ts.
 */
import type { BespokeContract } from '@core/catalog/contracts';

export type ContractModuleLoader = () => Promise<{ default: BespokeContract[] }>;

/** Bespoke namespace → its contracts module. */
export const contractModules: Record<string, ContractModuleLoader> = {
  rain: () => import('./sled/clients/rain/contracts'),
};
