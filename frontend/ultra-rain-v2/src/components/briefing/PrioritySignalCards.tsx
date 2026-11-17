import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, Zap } from 'lucide-react';
import type { Signal } from '@core/types';
import { Pill, type Tone } from '@/components/common/CardBits';

/**
 * A briefing's three priority signal cards, in full: severity, the headline
 * figure, what changed, the systems it was read from, and an action line.
 * Clicking a card asks its question. One column on a phone, three from the md
 * breakpoint. The manifest's `signalsComponent` slot.
 *
 * Two tenants drew this card identically apart from two words of copy, which
 * are props here:
 *   • `sourceSuffix` — appended to the source list (a data label, say).
 *   • `actionLine`   — what the arrow line under the card says: the signal's
 *     `trend` (always drawn), or the question its chip asks (drawn only when
 *     the signal has a chip).
 */
export interface PrioritySignalCardsProps {
  signals?: Signal[];
  visible?: boolean;
  signalToChip?: Record<string, string>;
  onInsightClick?: (chip: string) => void;
  /** Text appended after the joined sources, e.g. " · Synthetic". */
  sourceSuffix?: string;
  /** The arrow line: the signal's `trend`, or its chip's question. */
  actionLine?: 'trend' | 'chip';
}

const SEVERITY: Record<string, { tone: Tone; label: string; bar: string }> = {
  critical: { tone: 'critical', label: 'Critical', bar: 'bg-critical' },
  warning: { tone: 'warning', label: 'Warning', bar: 'bg-warning' },
  info: { tone: 'info', label: 'Info', bar: 'bg-info' },
};

export default function PrioritySignalCards({
  signals = [],
  visible = true,
  signalToChip = {},
  onInsightClick,
  sourceSuffix = '',
  actionLine = 'trend',
}: PrioritySignalCardsProps) {
  if (!signals.length) return null;
  return (
    <AnimatePresence>
      {visible && (
        <motion.section
          aria-label="Priority signals"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, height: 0, marginBottom: 0, overflow: 'hidden' }}
          transition={{ duration: 0.3 }}
          className="mb-3"
        >
          <div className="mb-2 flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-md bg-brand/10">
              <Zap className="h-3 w-3 text-brand" aria-hidden="true" />
            </span>
            <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">Priority signals</span>
            <span className="ml-1 h-px flex-1 bg-surface-2" />
          </div>
          <div className="grid gap-2.5 md:grid-cols-3">
            {signals.slice(0, 3).map((s) => {
              const sev = SEVERITY[String(s.severity)] ?? SEVERITY.info;
              const chip = signalToChip[s.id];
              const action = actionLine === 'chip' ? chip : s.trend;
              const showAction = actionLine === 'chip' ? Boolean(chip) : true;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => chip && onInsightClick?.(chip)}
                  className="group relative flex flex-col overflow-hidden rounded-xl border border-border bg-surface px-3 py-2.5 pl-4 text-left transition-shadow hover:border-brand/25 hover:shadow-[0_2px_8px_rgba(0,0,0,0.06)]"
                >
                  <span aria-hidden="true" className={`absolute inset-y-0 left-0 w-1 ${sev.bar}`} />
                  <span className="flex flex-wrap items-center justify-between gap-1.5">
                    <Pill tone={sev.tone}>{sev.label}</Pill>
                    {typeof s.metric_text === 'string' && <span className="text-[11px] font-semibold text-text">{s.metric_text}</span>}
                  </span>
                  <span className="mt-1 text-[13.5px] font-semibold leading-snug text-text">{s.title}</span>
                  <span className="mt-0.5 text-[12px] leading-snug text-text-muted">{s.description}</span>
                  <span className="mt-1 text-[10.5px] leading-snug text-text-subtle">{(s.sources ?? []).join(' · ')}{sourceSuffix}</span>
                  {showAction && (
                    <span className="mt-auto flex items-start gap-1 pt-1.5 text-[12px] font-semibold leading-snug text-brand">
                      <ArrowRight className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                      {action}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
