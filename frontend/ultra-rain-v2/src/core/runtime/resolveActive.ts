/**
 * resolveActive — pure resolution of the active Market → Client → Persona from
 * a clientId (from session) and an optional requested persona id (from URL).
 *
 * This replaces the CLIENT_PERSONAS allow-list + CLIENT_DEFAULT_PERSONA maps
 * that used to live inline in PersonaContext. Allow-listing is now implicit:
 * a persona is selectable iff it appears in its client's `personas` list.
 */

import { findClient } from './registry';
import type { ClientManifest, MarketManifest, PersonaModule } from '../types';

export interface ActiveResolution {
  market: MarketManifest;
  client: ClientManifest;
  persona: PersonaModule;
}

/**
 * Resolve the active persona. Returns null (→ caller falls back to the legacy
 * runtime) when:
 *   - no client id, or the client isn't registered yet, OR
 *   - a specific persona is requested but isn't registered yet.
 *
 * The second case is what makes partial migration safe: a registered client can
 * expose only some of its personas through the new runtime while the rest keep
 * rendering via the old path. When NO persona is requested, the client default
 * is used.
 */
export function resolveActive(
  clientId: string | null | undefined,
  requestedPersonaId?: string | null,
): ActiveResolution | null {
  if (!clientId) return null;
  const found = findClient(clientId);
  if (!found) return null;

  const { market, client } = found;

  let persona;
  if (requestedPersonaId) {
    persona = client.personas.find((p) => p.id === requestedPersonaId);
    if (!persona) return null; // requested but not yet migrated → legacy
  } else {
    persona =
      client.personas.find((p) => p.id === client.defaultPersonaId) ?? client.personas[0];
  }

  if (!persona) return null;
  return { market, client, persona };
}
