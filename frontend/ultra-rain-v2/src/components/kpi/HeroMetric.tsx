import { Link } from 'react-router-dom';
import { ArrowRight, CircleAlert, CircleCheck, CircleMinus, OctagonAlert } from 'lucide-react';
import { TrendBadge } from './Badges';
import Sparkline from './Sparkline';
import TargetBar, { type TargetBarProps } from './TargetBar';
import type { ComponentType, ReactNode } from 'react';

/**
 * KPI kit hero metric: the one number to look at first, on an inverse brand
 * surface so the eye goes there before anything else on the page. Figure at
 * 40–48px, status in a white pill, trend beside it, one line on why it
 * leads, the target bar and the trend line, and up to two actions.
 *
 * Props: eyebrow, title, to (title link), figure, words, period, status +
 * statusLabel, trend, why, detail (small lines), series, target, bar (see
 * TargetBar), seriesFrom/seriesTo labels, actions [{ label, to | onClick, icon, primary }].
 */
type KitStatus = 'good' | 'warn' | 'bad' | 'neutral';

const STATUS_ICON: Record<KitStatus, ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' }>> = { good: CircleCheck, warn: CircleAlert, bad: OctagonAlert, neutral: CircleMinus };

export interface HeroMetricAction {
  label: string;
  to?: string;
  onClick?: () => void;
  icon?: ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' }>;
  primary?: boolean;
}

export interface HeroMetricProps {
  eyebrow?: string;
  title: ReactNode;
  /** Makes the title a link. */
  to?: string;
  figure: ReactNode;
  words?: string;
  period?: string;
  status?: KitStatus;
  statusLabel?: string;
  /** The KPI kit's trend badge shape (see Badges). */
  trend?: { dir: 'up' | 'down' | 'flat'; tone: string; delta?: string; vs?: string; word?: string };
  why?: ReactNode;
  detail?: ReactNode;
  series?: number[];
  target?: number | null;
  bar?: TargetBarProps;
  seriesFrom?: string;
  seriesTo?: string;
  actions?: HeroMetricAction[];
  className?: string;
}

export default function HeroMetric({ eyebrow, title, to, figure, words, period, status = 'neutral', statusLabel, trend, why, detail, series, target = null, bar, seriesFrom, seriesTo, actions = [], className = '' }: HeroMetricProps) {
  const Icon = STATUS_ICON[status] ?? CircleMinus;
  return (
    <section aria-label={`${eyebrow ? `${eyebrow}: ` : ''}${title}`} className={`@container relative overflow-hidden rounded-2xl bg-brand p-4 text-white shadow-md sm:p-5 ${className}`}>
      <span aria-hidden="true" className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-white/[0.07]" />
      <div className="relative grid gap-4 @xl:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)] @xl:items-end">
        <div className="min-w-0">
          {eyebrow && <p className="text-[10.5px] font-bold uppercase tracking-[0.12em] text-white/85">{eyebrow}</p>}
          <h3 className="mt-1 text-[16px] font-bold leading-snug">
            {to ? (
              <Link to={to} className="hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">
                {title}
              </Link>
            ) : (
              title
            )}
          </h3>
          <p className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-[40px] font-bold leading-none tracking-tight tabular-nums @md:text-[48px]">{figure}</span>
            <span className="text-[12.5px] text-white/85">
              {words ? `${words} · ` : ''}
              {period}
            </span>
          </p>
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            {statusLabel && (
              <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-[12px] font-bold leading-tight text-brand">
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                {statusLabel}
              </span>
            )}
            <TrendBadge trend={trend} size="lg" inverse showVs />
          </div>
          {why && <p className="mt-2 text-[12.5px] leading-snug text-white/90">{why}</p>}
          {detail && <p className="mt-1 text-[11.5px] leading-snug text-white/85">{detail}</p>}
          {bar && <TargetBar {...bar} inverse className="mt-3 max-w-md" />}
        </div>
        <div className="min-w-0">
          {series && series.length > 1 && <Sparkline values={series} target={target} tone="inverse" width={320} height={84} />}
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            {seriesFrom ? (
              <span className="text-[11px] text-white/85">
                {seriesFrom} to {seriesTo}
              </span>
            ) : (
              <span />
            )}
            <span className="flex flex-wrap items-center justify-end gap-1.5">
              {actions.map((a) => {
                const cls = a.primary
                  ? 'inline-flex items-center gap-1.5 rounded-lg bg-white px-2.5 py-1.5 text-[12px] font-bold text-brand hover:bg-white/90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white'
                  : 'inline-flex items-center gap-1 rounded-lg bg-white/[0.14] px-2.5 py-1.5 text-[12px] font-bold hover:bg-white/[0.22] focus-visible:outline focus-visible:outline-2 focus-visible:outline-white';
                const ActionIcon = a.icon;
                const inner = (
                  <>
                    {ActionIcon && <ActionIcon className="h-3.5 w-3.5" aria-hidden="true" />}
                    {a.label}
                    {!a.primary && <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />}
                  </>
                );
                return a.to ? (
                  <Link key={a.label} to={a.to} className={cls}>
                    {inner}
                  </Link>
                ) : (
                  <button key={a.label} type="button" onClick={a.onClick} className={cls}>
                    {inner}
                  </button>
                );
              })}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
