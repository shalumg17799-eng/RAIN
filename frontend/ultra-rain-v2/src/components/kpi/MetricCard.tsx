import { Link } from 'react-router-dom';
import { StatusBadge, TrendBadge } from './Badges';
import Sparkline from './Sparkline';
import TargetBar from './TargetBar';
import type { ReactNode } from 'react';
import { STATUS, type KitStatus, type KitTrend, type TrendTone } from './tone';
import type { TargetBarProps } from './TargetBar';

/**
 * KPI kit metric card: one measure, scannable in a second. The figure is
 * large, the words around it are small, status and trend sit on one line,
 * and the right of the card carries the evidence (sparkline) so no space is
 * left empty. The left edge takes the status colour for scanning a grid by
 * colour first; the badge says it again in words.
 *
 * Props:
 *   title, to (link) or onClick, figure ("83%"), words ("Civil unlimited"),
 *   period, status + statusLabel, trend (see TrendBadge), series + target +
 *   seriesTone (sparkline), bar ({ value, target, max?, percent?, valueLabel?,
 *   targetLabel? } → TargetBar), footnote, eyebrow, size 'sm' | 'md',
 *   children (extra content under the main row).
 */
export interface MetricCardProps {
  title: ReactNode;
  /** A link… */
  to?: string;
  /** …or a button. Neither: a plain card. */
  onClick?: () => void;
  eyebrow?: ReactNode;
  figure?: string;
  words?: string;
  period?: string;
  status?: KitStatus;
  statusLabel?: string;
  trend?: KitTrend | null;
  /** Sparkline values. */
  series?: readonly (number | null | undefined)[] | null;
  target?: number | null;
  seriesTone?: TrendTone;
  bar?: Omit<TargetBarProps, 'status' | 'compact' | 'className'> | null;
  footnote?: ReactNode;
  size?: 'sm' | 'md';
  ariaLabel?: string;
  children?: ReactNode;
  className?: string;
}

export default function MetricCard({
  title,
  to,
  onClick,
  eyebrow,
  figure,
  words,
  period,
  status = 'neutral',
  statusLabel,
  trend,
  series,
  target = null,
  seriesTone,
  bar,
  footnote,
  size = 'sm',
  ariaLabel,
  children,
  className = '',
}: MetricCardProps) {
  const s = STATUS[status] ?? STATUS.neutral;
  const md = size === 'md';
  const body = (
    <>
      {eyebrow && <span className="mb-0.5 block truncate text-[10.5px] font-semibold text-brand">{eyebrow}</span>}
      <span className={`block font-semibold leading-snug text-text group-hover:text-brand ${md ? 'text-[13.5px]' : 'line-clamp-2 text-[12.5px]'}`}>{title}</span>
      <span className="mt-1.5 flex items-end justify-between gap-3">
        <span className="min-w-0">
          <span className={`block font-bold leading-none tracking-tight tabular-nums text-text ${md ? 'text-[30px]' : figure && figure.length > 8 ? 'text-[17px]' : 'text-[24px]'}`}>{figure}</span>
          <span className={`mt-1 block text-[10.5px] leading-tight text-text-muted ${md ? '' : 'truncate'}`} title={md ? undefined : [words, period].filter(Boolean).join(' · ')}>
            {words ? `${words} · ` : ''}
            {period}
          </span>
        </span>
        {series && series.length > 1 && (
          <span className="flex-shrink-0">
            <Sparkline values={series} width={md ? 128 : 76} height={md ? 40 : 28} target={target} tone={seriesTone ?? trend?.tone} />
          </span>
        )}
      </span>
      {bar && <TargetBar {...bar} status={status} compact={!md} className="mt-2" />}
      <span className="mt-2 flex flex-wrap items-center gap-1">
        {statusLabel && <StatusBadge status={status} label={statusLabel} />}
        <TrendBadge trend={trend} />
      </span>
      {footnote && <span className="mt-1.5 block text-[11px] leading-snug text-text-muted">{footnote}</span>}
    </>
  );
  const cls = `group relative flex h-full min-w-0 flex-col overflow-hidden rounded-xl border border-border bg-surface p-3 pl-3.5 text-left shadow-sm transition-[border-color,box-shadow] before:absolute before:inset-y-0 before:left-0 before:w-1 hover:border-brand/40 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand ${s.edge} ${className}`;
  if (to)
    return (
      <Link to={to} aria-label={ariaLabel} className={cls}>
        {body}
        {children}
      </Link>
    );
  if (onClick)
    return (
      <button type="button" onClick={onClick} aria-label={ariaLabel} className={cls}>
        {body}
        {children}
      </button>
    );
  return (
    <div className={cls} aria-label={ariaLabel} role={ariaLabel ? 'group' : undefined}>
      {body}
      {children}
    </div>
  );
}
