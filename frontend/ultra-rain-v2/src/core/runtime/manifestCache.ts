/**
 * Loaded persona manifests, by persona module.
 *
 * A manifest's chunk is fetched once; after that, anything that needs the
 * active persona's manifest (the workspace, a shared page asking for the
 * persona's own variant) can read it synchronously instead of rendering a
 * blank frame while a promise it has already resolved settles again.
 * Keyed by module object because persona ids repeat across clients (the
 * shared ops/cx/retention/risk personas), while modules do not.
 */
import type { PersonaManifest, PersonaModule } from '../types';

const cache = new WeakMap<PersonaModule, PersonaManifest>();
// One load per module, shared by every concurrent caller. Factory personas
// (the shared ops/cx/retention/risk, SCLAC's KPI personas) build a NEW manifest
// object on each `load()`, so two consumers loading at once would otherwise
// each hold a different object for the same persona.
const inflight = new WeakMap<PersonaModule, Promise<PersonaManifest>>();

export function getCachedManifest(module: PersonaModule): PersonaManifest | undefined {
  return cache.get(module);
}

export function loadManifest(module: PersonaModule): Promise<PersonaManifest> {
  const hit = cache.get(module);
  if (hit) return Promise.resolve(hit);
  let pending = inflight.get(module);
  if (!pending) {
    pending = module.load().then(
      (mod) => {
        cache.set(module, mod.default);
        inflight.delete(module);
        return mod.default;
      },
      (err) => {
        inflight.delete(module);
        throw err;
      },
    );
    inflight.set(module, pending);
  }
  return pending;
}
