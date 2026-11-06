/**
 * Zod-free helpers for reading component specs off a message. The workspace
 * calls these on every AI turn, so they stay out of the schema module and the
 * main bundle does not carry zod for them.
 */

export interface ContractSpec {
  type: string;
  version: number;
  props: Record<string, unknown>;
}

/**
 * A legacy `ui_components_to_render` entry carries its props flat beside
 * `type`, and most of them are drawn by a persona's `answers` hook
 * rather than by type. Only entries written in the contract form —
 * `{ type, version?, props }` — are drawn by the catalog renderer, so legacy
 * entries can never start rendering by accident when a catalog type is added
 * with the same name.
 */
export function isContractSpec(entry: unknown): entry is ContractSpec {
  if (!entry || typeof entry !== 'object') return false;
  const e = entry as { type?: unknown; props?: unknown };
  return typeof e.type === 'string' && e.type.length > 0 && typeof e.props === 'object' && e.props !== null && !Array.isArray(e.props);
}

/** The contract-form components of a legacy list, with `version` defaulted to 1. */
export function contractComponents(entries: unknown): ContractSpec[] {
  if (!Array.isArray(entries)) return [];
  return entries.filter(isContractSpec).map((e) => ({ type: e.type, version: typeof e.version === 'number' ? e.version : 1, props: e.props }));
}
