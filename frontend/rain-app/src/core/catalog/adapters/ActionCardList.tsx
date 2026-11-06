/**
 * `action_cards` — a list of ActionCard, the shape the workspace used to build
 * by hand for inline personas. Confirming one reports its id through the
 * renderer's `onAction`, which the workspace wires to the persona's
 * action-confirm flow.
 */
import { useState, type ComponentType } from 'react';
import ActionCardJsx from '@/components/cards/ActionCard';

// ActionCard is untyped JSX whose optional props infer as required.
const ActionCard = ActionCardJsx as unknown as ComponentType<Record<string, unknown>>;

interface Action { id: string; [key: string]: unknown }

export default function ActionCardList({ actions, confirmLabel, onAction }: { actions: Action[]; confirmLabel?: string; onAction?: (id: string) => void }) {
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
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
        />
      ))}
    </div>
  );
}
