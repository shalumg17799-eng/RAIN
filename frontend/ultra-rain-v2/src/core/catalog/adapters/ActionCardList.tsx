/**
 * `action_cards` — a list of ActionCard, the shape the workspace used to build
 * by hand for inline personas. Confirming one reports its id through the
 * renderer's `onAction`, which the workspace wires to the persona's
 * action-confirm flow.
 */
import { useState, type ComponentType } from 'react';
import ActionCardJsx from '@/components/cards/ActionCard';

// Catalog actions are loose records (title and system are optional in the contract); ActionCard's props require them.
const ActionCard = ActionCardJsx as unknown as ComponentType<Record<string, unknown>>;

interface Action { id: string; [key: string]: unknown }

export default function ActionCardList({ actions, confirmLabel, confirmedIds, onAction }: { actions: Action[]; confirmLabel?: string; confirmedIds?: string[]; onAction?: (id: string) => void }) {
  // Actions the client's store already holds as approved start confirmed.
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>(() => Object.fromEntries((confirmedIds ?? []).map((id) => [id, true])));
  return (
    <div className="space-y-3">
      {actions.map((action) => (
        <ActionCard
          key={action.id}
          action={action}
          isConfirmed={!!confirmed[action.id]}
          confirmLabel={confirmLabel}
          onConfirm={() => { setConfirmed((c) => ({ ...c, [action.id]: true })); onAction?.(action.id); }}
          onEdit={() => {}}
        >
          {Array.isArray(action.details) && action.details.length > 0 ? (
            <details className="mt-2 text-[12px] text-text-muted">
              <summary className="cursor-pointer font-semibold text-text">Details</summary>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {(action.details as string[]).map((line) => <li key={line}>{line}</li>)}
              </ul>
            </details>
          ) : undefined}
        </ActionCard>
      ))}
    </div>
  );
}
