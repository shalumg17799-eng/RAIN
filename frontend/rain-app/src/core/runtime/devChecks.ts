/**
 * Development-only manifest checks, run as each persona loads.
 *
 * The same schema runs in CI (manifests.test.ts), but a tenant being built
 * locally should not have to wait for the test run to learn that its manifest
 * is malformed. Production builds strip this: `import.meta.env.DEV` is a
 * compile-time constant, so the whole call is dead code there.
 */
import { validateManifest } from './validate';
import { devError } from '../log';

const reported = new Set<string>();

export function checkManifestInDev(manifest: unknown): void {
  if (!import.meta.env.DEV) return;
  const { ok, errors } = validateManifest(manifest);
  if (ok) return;
  const id =
    manifest && typeof manifest === 'object' && 'id' in manifest ? String((manifest as { id: unknown }).id) : '(unknown)';
  if (reported.has(id)) return;
  reported.add(id);
  devError(`[ultra] Persona manifest "${id}" does not satisfy the standard:\n  - ${errors.join('\n  - ')}`);
}
