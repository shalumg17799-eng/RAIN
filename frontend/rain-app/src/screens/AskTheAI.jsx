/**
 * AskTheAI — the /ask route. A thin router over the market registry: it resolves
 * the active persona from the session's client + the URL persona and renders the
 * generic, manifest-driven PersonaWorkspace.
 *
 * (Was a 1,276-line god-screen with ~40 static tenant imports and hand-maintained
 * per-persona registries; the North Star refactor moved all of that into
 * per-persona manifest modules under src/markets — see the plan.)
 */

import { usePersona } from '../context/PersonaContext';
import { useBranding } from '../context/BrandingContext';
import { useActivePersona } from '@core/runtime/useActivePersona';
import PersonaWorkspace from '../shared/workspace/PersonaWorkspace';
import PageErrorBoundary from '../components/common/PageErrorBoundary';

export default function AskTheAI() {
  const persona = usePersona();
  const { clientId } = useBranding();
  const active = useActivePersona(clientId, persona.id);

  if (active.status === 'ready' && active.manifest) {
    return (
      <PageErrorBoundary resetKey={active.manifest.id} label="workspace">
        <PersonaWorkspace manifest={active.manifest} />
      </PageErrorBoundary>
    );
  }
  if (active.status === 'error') {
    // The persona's code chunk did not arrive (typically a deploy landed
    // mid-session). A reload fetches the current chunks.
    return (
      <div className="flex-1 flex items-center justify-center p-6" role="alert">
        <div className="max-w-sm w-full bg-surface rounded-xl border border-border px-5 py-4">
          <p className="text-sm font-semibold text-text">This workspace couldn&apos;t be loaded</p>
          <p className="text-xs text-text-muted mt-1">A newer version of the app may be available.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-3 rounded-lg border border-border px-2.5 py-1 text-xs font-semibold text-text-muted hover:text-brand hover:border-brand/30 transition-colors"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
  // Briefly null while the persona's chunk loads. Every selectable persona is
  // registered, so `unregistered` is not reachable in normal operation.
  return null;
}
