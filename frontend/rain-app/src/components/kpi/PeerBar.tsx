/**
 * KPI kit peer bar: one site's value against its peers' median on a shared
 * scale, for comparison tables. The bar is the value; the tick is the peer
 * median; the colour says whether the gap is good or bad for the measure
 * (`higherIsBetter`). No ranking is implied: each row reads against its own
 * peers, and the number is always printed beside the bar.
 *
 * Props: value, peer (median or null), min, max, higherIsBetter, valueLabel.
 */
export interface PeerBarProps {
  value: number | null | undefined;
  peer?: number | null;
  min?: number;
  max?: number;
  higherIsBetter?: boolean;
  valueLabel?: string | null;
  className?: string;
}

export default function PeerBar({ value, peer = null, min = 0, max = 100, higherIsBetter = true, valueLabel, className = '' }: PeerBarProps) {
  if (value == null || Number.isNaN(value)) return null;
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / (max - min || 1)) * 100))}%`;
  const gap = peer == null ? 0 : value - peer;
  const good = peer == null || gap === 0 ? null : gap > 0 === higherIsBetter;
  const fill = good == null ? 'bg-brand/60' : good ? 'bg-success' : 'bg-critical';
  return (
    <span className={`flex min-w-[96px] items-center gap-2 ${className}`}>
      <span className="relative h-2 flex-1 rounded-full bg-surface-2 ring-1 ring-inset ring-border-subtle" aria-hidden="true">
        <span className={`absolute inset-y-0 left-0 rounded-full ${fill}`} style={{ width: pos(value) }} />
        {peer != null && <span className="absolute -top-1 -bottom-1 w-0.5 -translate-x-1/2 rounded-full bg-text" style={{ left: pos(peer) }} />}
      </span>
      {valueLabel != null && <span className="w-12 flex-shrink-0 text-right text-[12px] font-semibold tabular-nums text-text">{valueLabel}</span>}
    </span>
  );
}
