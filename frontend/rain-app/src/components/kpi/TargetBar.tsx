import { STATUS, type KitStatus } from './tone';

/**
 * KPI kit target bar (a bullet chart): where a value sits against its target
 * on one track. The fill takes the status colour, a tick marks the target,
 * and the gap reads at a glance: "73% against a 95% floor" becomes a red bar
 * stopping well short of the line. Works for lower-is-better measures too:
 * the target tick is drawn where it is and the words say which side is good.
 *
 * Props: value, target (number or null), min (default 0), max (default the
 * larger of value and target, padded; 100 for percentages via `percent`),
 * status, valueLabel/targetLabel (words under the bar), compact.
 */
export interface TargetBarProps {
  value: number | null | undefined;
  target?: number | null;
  min?: number;
  max?: number;
  percent?: boolean;
  status?: KitStatus;
  valueLabel?: string;
  targetLabel?: string;
  compact?: boolean;
  /** Drawn on a brand surface. */
  inverse?: boolean;
  className?: string;
}

export default function TargetBar({ value, target = null, min = 0, max, percent = false, status = 'neutral', valueLabel, targetLabel, compact = false, inverse = false, className = '' }: TargetBarProps) {
  if (value == null || Number.isNaN(value)) return null;
  const top = max ?? (percent ? 100 : Math.max(value, target ?? value) * 1.2 || 1);
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / (top - min || 1)) * 100))}%`;
  const s = STATUS[status] ?? STATUS.neutral;
  const h = compact ? 'h-1.5' : 'h-2.5';
  const label = `${valueLabel ?? value}${target != null && targetLabel ? `, ${targetLabel}` : ''}`;
  return (
    <div className={`min-w-0 ${className}`} role="img" aria-label={label}>
      <div className={`relative ${h} w-full rounded-full ${inverse ? 'bg-white/20' : 'bg-surface-2 ring-1 ring-inset ring-border-subtle'}`}>
        <div className={`absolute inset-y-0 left-0 rounded-full ${inverse ? 'bg-white' : s.fill}`} style={{ width: pos(value) }} />
        {target != null && (
          <span
            className={`absolute -top-1 -bottom-1 w-0.5 -translate-x-1/2 rounded-full ${inverse ? 'bg-white/90' : 'bg-text'}`}
            style={{ left: pos(target) }}
            aria-hidden="true"
          />
        )}
      </div>
      {!compact && (valueLabel || targetLabel) && (
        <div className={`mt-1 flex items-baseline justify-between gap-2 text-[10.5px] ${inverse ? 'text-white/85' : 'text-text-muted'}`} aria-hidden="true">
          <span className="truncate">{valueLabel}</span>
          {target != null && targetLabel && <span className="flex-shrink-0">{targetLabel}</span>}
        </div>
      )}
    </div>
  );
}
