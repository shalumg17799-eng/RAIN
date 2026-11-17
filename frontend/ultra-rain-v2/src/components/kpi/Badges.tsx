import { ArrowDownRight, ArrowRight, ArrowUpRight, CircleAlert, CircleCheck, CircleMinus, OctagonAlert } from 'lucide-react';
import { STATUS, TREND_PILL, TREND_PILL_INVERSE } from './tone';
import type { ComponentType, ReactNode } from 'react';
import type { KitStatus } from './tone';

type Icon = ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' | 'false' }>;

/** STATUS and TREND_PILL, read by any word (an unknown one is undefined, so the fallback applies). */
const STATUS_BY: Record<string, (typeof STATUS)[KitStatus] | undefined> = STATUS;
const TREND_PILL_BY: Record<string, string | undefined> = TREND_PILL;

export interface StatusBadgeProps {
  /** good · warn · bad · neutral; anything else draws as neutral. */
  status?: KitStatus | string;
  label?: ReactNode;
  size?: 'sm' | 'lg';
  className?: string;
}

/** A trend as the badge reads it (a KitTrend, or any record with the same words). */
export interface TrendBadgeTrend {
  /** up · down · flat */
  dir: string;
  /** improving · worsening · steady · neutral */
  tone: string;
  delta?: string;
  word?: string;
  vs?: string;
}

export interface TrendBadgeProps {
  trend?: TrendBadgeTrend | null;
  size?: 'sm' | 'lg';
  /** Drawn on a brand surface. */
  inverse?: boolean;
  /** Show the comparison (otherwise screen-reader only). */
  showVs?: boolean;
  className?: string;
}

/**
 * KPI kit badges. StatusBadge: where a number stands (word + icon + colour).
 * TrendBadge: whether it is getting better or worse (arrow + change + word),
 * coloured by what the move means, not by its direction.
 */

const STATUS_ICON: Record<string, Icon | undefined> = { good: CircleCheck, warn: CircleAlert, bad: OctagonAlert, neutral: CircleMinus };

export function StatusBadge({ status = 'neutral', label, size = 'sm', className = '' }: StatusBadgeProps) {
  const s = STATUS_BY[status] ?? STATUS.neutral;
  const Icon = STATUS_ICON[status] ?? CircleMinus;
  const pad = size === 'lg' ? 'gap-1 px-2.5 py-1 text-[12px]' : 'gap-1 px-2 py-0.5 text-[11px]';
  return (
    <span className={`inline-flex flex-shrink-0 items-center rounded-full border font-semibold leading-tight ${pad} ${s.badge} ${className}`}>
      <Icon className={size === 'lg' ? 'h-3.5 w-3.5' : 'h-3 w-3'} aria-hidden="true" />
      {label}
    </span>
  );
}

const ARROW: Record<string, Icon | undefined> = { up: ArrowUpRight, down: ArrowDownRight, flat: ArrowRight };

/**
 * `trend`: { dir: 'up'|'down'|'flat', tone: 'improving'|'worsening'|'steady'|'neutral',
 * delta?: '+30 cases', vs?: 'vs Sep 2025', word: 'Worsening' }.
 */
export function TrendBadge({ trend, size = 'sm', inverse = false, showVs = false, className = '' }: TrendBadgeProps) {
  if (!trend || (!trend.delta && !trend.word)) return null;
  const Icon = ARROW[trend.dir] ?? ArrowRight;
  const cls = inverse ? TREND_PILL_INVERSE : TREND_PILL_BY[trend.tone] ?? TREND_PILL.steady;
  const pad = size === 'lg' ? 'gap-1 px-2.5 py-1 text-[12.5px]' : 'gap-0.5 px-2 py-0.5 text-[11px]';
  return (
    <span className={`inline-flex flex-shrink-0 items-center rounded-full border font-semibold leading-tight tabular-nums ${pad} ${cls} ${className}`}>
      <Icon className={size === 'lg' ? 'h-3.5 w-3.5' : 'h-3 w-3'} aria-hidden="true" />
      {trend.delta && <span>{trend.delta}</span>}
      {trend.delta && trend.word && <span aria-hidden="true">·</span>}
      {trend.word && <span>{trend.word}</span>}
      {trend.vs && (showVs ? <span className="font-medium opacity-80">{trend.vs}</span> : <span className="sr-only">{trend.vs}</span>)}
    </span>
  );
}
