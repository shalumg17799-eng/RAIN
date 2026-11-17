/**
 * Registry accessors for component contracts: where each bespoke namespace's
 * `contracts.ts` lives (src/markets/contracts.ts) and which retired type ids
 * resolve to which type (src/markets/aliases.ts). Imported only by the lazy
 * contract layer (core/catalog), the tests and the scripts — never the startup
 * bundle: retired ids are resolved where data enters (the API boundary), and
 * recorded answers only use live ids (contracts.test.tsx).
 */
import { contractModules, type ContractModuleLoader } from '@markets/contracts';
import { typeAliases } from '@markets/aliases';

/** Retired component type ids → the type that replaced each (core/catalog/contract). */
export function getTypeAliases(): Readonly<Record<string, string>> {
  return typeAliases;
}

/** The lazy loader of a bespoke namespace's contracts (`<client>/contracts.ts`), if it has one. */
export function getContractModule(namespace: string): ContractModuleLoader | undefined {
  return contractModules[namespace];
}

/** Every bespoke namespace that declares contracts. */
export function getContractNamespaces(): string[] {
  return Object.keys(contractModules);
}
