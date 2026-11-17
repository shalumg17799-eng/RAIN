/**
 * Development-only manifest checks, run as each persona loads.
 *
 * The same schema runs in CI (manifests.test.ts), but a tenant being built
 * locally should not have to wait for the test run to learn that its manifest
 * is malformed. Production builds strip this: `import.meta.env.DEV` is a
 * compile-time constant, so the whole call is dead code there.
 */
import { validateManifest } from './validate';
import type { PersonaManifest } from '../types';
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

const answersReported = new Set<string>();

/**
 * Development only: every recorded answer of the persona against its
 * component contracts (core/catalog/contracts), so a tenant being built sees a
 * payload that drifted from its contract as it loads, not at the next test run.
 * Runs after the persona has drawn, off the critical path.
 */
export function checkAnswersInDev(manifest: PersonaManifest): void {
  if (!import.meta.env.DEV || answersReported.has(manifest.id)) return;
  answersReported.add(manifest.id);
  setTimeout(() => {
    void import('../catalog/contracts').then(async ({ checkSpec }) => {
      const problems: string[] = [];
      for (const [flowKey, flow] of Object.entries(manifest.flows.chatFlows)) {
        const ui = (flow as { ui_components_to_render?: unknown[] }).ui_components_to_render ?? [];
        for (const spec of manifest.answers?.({ flowKey, role: 'ai', uiComponents: ui }, manifest.signals ?? []) ?? []) {
          const r = await checkSpec(spec);
          if (!r.ok) problems.push(`${flowKey} · ${spec.type}: ${r.issues.join('; ')}`);
        }
      }
      if (problems.length) devError(`[ultra] Persona "${manifest.id}" answers that break their component contracts:\n  - ${problems.slice(0, 20).join('\n  - ')}`);
    });
  }, 1500);
}

