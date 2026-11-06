import { Info, RotateCcw } from 'lucide-react';

/**
 * The one-line prototype notice pinned under the chat input (a persona's
 * `workspaceFooter`), with an optional Reset.
 *
 * Promoted from the Comptroller of Maryland's IllustrativeFooter, which renders
 * through this unchanged, so every tenant that discloses illustrative data
 * says it in the same place and the same way. `children` render after the
 * line (the Comptroller's toasts, SCLAC's evidence drawer).
 */
export default function PrototypeFooter({
  text = 'Illustrative prototype. Data, people and results are illustrative. Public facts are cited.',
  onRestart,
  restartTitle = 'Reset the demo',
  children,
}) {
  return (
    <div className="mt-2 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-center text-[11px] leading-snug text-text-subtle">
      <span className="inline-flex items-center gap-1.5">
        <Info className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
        {text}
      </span>
      {onRestart && (
        <button
          type="button"
          onClick={onRestart}
          aria-label="Reset demo"
          title={restartTitle}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold text-text-muted hover:bg-surface-2 hover:text-text"
        >
          <RotateCcw className="h-3 w-3" aria-hidden="true" />
          Reset demo
        </button>
      )}
      {children}
    </div>
  );
}
