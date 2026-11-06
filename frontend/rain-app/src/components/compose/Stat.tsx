/** Tier 3 stat tile: one figure with its label, status and trend in words. */
import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react';
import { ICONS } from '@core/contract/icons';
import { toStatus, STATUS_STYLE, type Trend } from '@core/contract/status';

export interface StatProps {
  label: string;
  value: string;
  caption?: string;
  status?: string;
  trend?: Trend;
  /** Icon registry id, e.g. `users`. */
  icon?: string;
}

const ARROW = { up: ArrowUpRight, down: ArrowDownRight, flat: ArrowRight };

export function Stat({ label, value, caption, status, trend, icon }: StatProps) {
  const Icon = icon ? ICONS[icon] : undefined;
  const s = status ? STATUS_STYLE[toStatus(status)] : null;
  const TrendIcon = trend ? ARROW[trend.direction] : null;
  const trendTone = trend?.good === undefined ? 'text-text-muted' : trend.good ? 'text-success' : 'text-critical';
  return (
    <div className="rounded-xl border border-border bg-surface px-4 py-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="h-3.5 w-3.5 text-text-subtle" aria-hidden="true" />}
        <p className="truncate text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      </div>
      <p className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-text">{value}</p>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
        {s && (
          <span className={`inline-flex items-center gap-1 font-semibold ${s.text}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden="true" />
            {s.label}
          </span>
        )}
        {trend && TrendIcon && (
          <span className={`inline-flex items-center gap-0.5 font-semibold ${trendTone}`}>
            <TrendIcon className="h-3 w-3" aria-hidden="true" />
            {trend.label ?? (trend.value !== undefined ? `${trend.value}` : '')}
          </span>
        )}
        {caption && <span className="text-text-subtle">{caption}</span>}
      </div>
    </div>
  );
}
