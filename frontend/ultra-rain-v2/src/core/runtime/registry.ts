/**
 * Registry accessors — the runtime's read API over the market registry.
 *
 * The app never imports a tenant module directly; it asks the registry. Client
 * ids are unique across markets, so client/persona lookups search all markets
 * (until the Market axis becomes an explicit selection in Phase 6).
 */

import { marketRegistry } from '@markets';
import type { ClientManifest, MarketManifest, PersonaModule } from '../types';

export function getMarkets(): MarketManifest[] {
  return marketRegistry;
}

export function getMarket(marketId: string): MarketManifest | null {
  return marketRegistry.find((d) => d.id === marketId) ?? null;
}

/** Find a client (and its owning market) by client id, across all markets. */
export function findClient(
  clientId: string,
): { market: MarketManifest; client: ClientManifest } | null {
  for (const market of marketRegistry) {
    const client = market.clients.find((c) => c.id === clientId);
    if (client) return { market, client };
  }
  return null;
}

/** Whether a client has been migrated into the new registry yet. */
export function isClientRegistered(clientId: string): boolean {
  return findClient(clientId) !== null;
}

/** Persona modules a client exposes, in display order. */
export function getClientPersonas(clientId: string): PersonaModule[] {
  return findClient(clientId)?.client.personas ?? [];
}

export function getPersonaModule(clientId: string, personaId: string): PersonaModule | null {
  return getClientPersonas(clientId).find((p) => p.id === personaId) ?? null;
}
