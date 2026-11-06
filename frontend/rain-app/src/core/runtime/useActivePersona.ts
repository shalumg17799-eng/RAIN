/**
 * useActivePersona — resolves and lazily loads the active persona's manifest.
 *
 * Given the session's clientId and the URL's persona id, it resolves via the
 * registry and dynamically imports the persona module (per-tenant code-split).
 * Returns `status: 'unregistered'` when the client hasn't been migrated into the
 * new registry yet — the caller then falls back to the legacy runtime. This is
 * the seam that lets old and new render paths coexist during the migration.
 */

import { useEffect, useMemo, useState } from 'react';
import { resolveActive } from './resolveActive';
import { getCachedManifest, loadManifest } from './manifestCache';
import type { PersonaManifest, PersonaModule } from '../types';

export type ActivePersonaStatus = 'unregistered' | 'loading' | 'ready' | 'error';

export interface ActivePersonaState {
  status: ActivePersonaStatus;
  manifest: PersonaManifest | null;
  /** The resolved persona id (may differ from requested when a default kicks in). */
  personaId: string | null;
  clientId: string | null;
  /** Set when the persona's chunk failed to load (e.g. a stale deploy). */
  error?: Error;
}

export function useActivePersona(
  clientId: string | null | undefined,
  requestedPersonaId?: string | null,
): ActivePersonaState {
  const resolution = useMemo(
    () => resolveActive(clientId, requestedPersonaId),
    [clientId, requestedPersonaId],
  );

  // A manifest loaded before (on /ask, or by another consumer) is available on
  // the first render — no blank frame while an already-settled load re-settles.
  const [loaded, setLoaded] = useState<{ key: string; module: PersonaModule; manifest: PersonaManifest } | null>(() => {
    const cached = resolution && getCachedManifest(resolution.persona);
    return cached ? { key: resolution.persona.id, module: resolution.persona, manifest: cached } : null;
  });
  const [failed, setFailed] = useState<{ key: string; error: Error } | null>(null);

  useEffect(() => {
    if (!resolution) return;
    let cancelled = false;
    const cached = getCachedManifest(resolution.persona);
    if (cached) {
      // Synchronously available (see the initializer); only switch if a
      // different persona was showing.
      setLoaded((prev) => (prev?.module === resolution.persona ? prev : { key: resolution.persona.id, module: resolution.persona, manifest: cached }));
      return undefined;
    }
    loadManifest(resolution.persona).then(
      (manifest) => {
        if (cancelled) return;
        // Dynamic and inside a compile-time DEV branch, so neither the check
        // nor zod reaches the production entry chunk.
        if (import.meta.env.DEV) void import('./devChecks').then((m) => m.checkManifestInDev(manifest));
        setLoaded({ key: resolution.persona.id, module: resolution.persona, manifest });
      },
      // A chunk that fails to load used to leave /ask blank with an unhandled
      // rejection. Surfacing it lets the route say so and offer a reload.
      (error: unknown) => {
        if (!cancelled) setFailed({ key: resolution.persona.id, error: error instanceof Error ? error : new Error(String(error)) });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [resolution]);

  if (!resolution) {
    return { status: 'unregistered', manifest: null, personaId: requestedPersonaId ?? null, clientId: clientId ?? null };
  }

  if (failed?.key === resolution.persona.id && loaded?.key !== resolution.persona.id) {
    return { status: 'error', manifest: null, personaId: resolution.persona.id, clientId: clientId ?? null, error: failed.error };
  }

  // Ready when the manifest held was loaded for this resolution's module — not
  // merely one with the same id, since shared persona ids repeat across clients.
  const ready = !!loaded && loaded.module === resolution.persona;
  return {
    status: ready ? 'ready' : 'loading',
    manifest: ready ? loaded!.manifest : null,
    personaId: resolution.persona.id,
    clientId: clientId ?? null,
  };
}
