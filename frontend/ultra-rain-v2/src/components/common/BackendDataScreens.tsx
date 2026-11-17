/**
 * What the app shows before its data arrives from the backend, and instead of
 * the app when the backend cannot deliver it. RAIN never renders local data,
 * so these screens carry no figures, only where the data is expected from.
 */

import type { ReactNode } from 'react';

function Centered({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-page p-6 text-text">
      <div className="max-w-xl rounded-lg border border-border bg-surface p-6 shadow-sm">{children}</div>
    </main>
  );
}

export function LoadingBackendData({ url }: { url: string }) {
  return (
    <Centered>
      <p className="text-sm text-text-secondary">Loading RAIN data from the backend ({url})…</p>
    </Centered>
  );
}

export function BackendUnavailable({ url, error, onRetry }: { url: string; error: unknown; onRetry: () => void }) {
  const e = error as { url?: string; message?: string } | undefined;
  return (
    <Centered>
      <h1 className="text-lg font-semibold">RAIN could not load its data from the backend</h1>
      <p className="mt-2 text-sm text-text-secondary">Every value in RAIN is served by the backend, and nothing is shown without it.</p>
      <p className="mt-3 break-all rounded bg-surface-subtle p-2 font-mono text-xs">
        GET {e?.url ?? url}: {e?.message ?? String(error)}
      </p>
      <button type="button" className="mt-4 rounded bg-brand px-3 py-1.5 text-sm font-medium text-white" onClick={onRetry}>
        Try again
      </button>
    </Centered>
  );
}
