import { motion } from 'framer-motion';
import { Ticket, Calendar, FileText, Check, Pencil } from 'lucide-react';
import { tierFor, colorFor, bgFor, borderFor } from '@/utils/confidence';

const iconMap = {
  'JIRA': Ticket,
  'Calendar / Salesforce': Calendar,
  'Report Engine': FileText,
};

/**
 * The recommended-action card.
 *
 * Optional props (all absent for the original callers, which render exactly as
 * before): `icon` overrides the system icon; `children` renders the draft under
 * the description (SCLAC shows the slide, email or ticket it will send);
 * `confirmLabel` / `editLabel` / `confirmedText` rename the controls; `onDismiss`
 * adds a Dismiss button and `isDismissed` shows that state; `confirmedNote`
 * adds a line under the confirmed state; `confirmedTextClassName` recolours the
 * confirmed line (SCLAC needs 4.5:1 on the green fill; the default is unchanged).
 */
export default function ActionCard({
  action,
  onConfirm,
  onEdit,
  isConfirmed,
  icon,
  children,
  confirmLabel = 'Confirm',
  editLabel = 'Edit First',
  confirmedText = 'Confirmed',
  confirmedNote,
  onDismiss,
  isDismissed = false,
  confirmedTextClassName = 'text-success-600',
}) {
  const Icon = icon || iconMap[action.system] || FileText;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`rounded-xl border p-4 transition-all ${
        isConfirmed
          ? 'border-success-200 bg-success-50'
          : isDismissed
            ? 'border-border bg-surface-2'
            : 'border-border bg-surface hover:border-border hover:shadow-sm'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
          isConfirmed ? 'bg-success-100' : 'bg-brand/10'
        }`}>
          {isConfirmed ? (
            <Check className="w-4 h-4 text-success-600" />
          ) : (
            <Icon className="w-4 h-4 text-brand" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h4 className="text-sm font-semibold text-text">{action.title}</h4>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-muted font-medium">{action.system}</span>
            {action.confidence && (() => {
              const tier = tierFor(action.confidence.score);
              return (
                <span
                  className="text-[10px] font-semibold tabular-nums px-1.5 py-0.5 rounded"
                  style={{ color: colorFor(tier), background: bgFor(tier), border: `1px solid ${borderFor(tier)}` }}
                >
                  Confidence {action.confidence.score}%
                </span>
              );
            })()}
          </div>
          <p className="text-xs text-text-muted leading-relaxed mb-3">{action.description}</p>
          {children && <div className="mb-3 min-w-0">{children}</div>}
          {!isConfirmed && !isDismissed && (
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => onConfirm(action.id)}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-brand hover:bg-brand/90 transition-colors cursor-pointer"
              >
                {confirmLabel}
              </button>
              <button
                onClick={() => onEdit?.(action.id)}
                className="px-4 py-1.5 rounded-lg text-xs font-medium text-text-muted bg-surface-2 hover:bg-border transition-colors cursor-pointer flex items-center gap-1"
              >
                <Pencil className="w-3 h-3" />
                {editLabel}
              </button>
              {onDismiss && (
                <button
                  onClick={() => onDismiss(action.id)}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium text-text-muted hover:bg-surface-2 transition-colors cursor-pointer"
                >
                  Dismiss
                </button>
              )}
            </div>
          )}
          {isConfirmed && (
            <>
              <p className={`text-xs font-medium ${confirmedTextClassName}`}>{confirmedText}</p>
              {confirmedNote && <p className="mt-0.5 text-[11px] text-text-muted">{confirmedNote}</p>}
            </>
          )}
          {isDismissed && <p className="text-xs font-medium text-text-muted">Dismissed. Nothing was sent.</p>}
        </div>
      </div>
    </motion.div>
  );
}
