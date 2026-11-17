/**
 * Retired component type ids, and the type that replaced each — the half of
 * the component registry the chat reads synchronously (core/catalog/contract:
 * `canonicalType`). Kept apart from the contract loaders (./contracts.ts) so
 * the startup bundle carries only this table.
 */
/**
 * Retired type id → the type that replaced it. An answer, a stored
 * conversation or an API payload that still sends the old id draws the new
 * type with the same props; the contract test proves each alias resolves.
 * Remove an alias only when nothing can still send it.
 */
export const typeAliases: Record<string, string> = {};
