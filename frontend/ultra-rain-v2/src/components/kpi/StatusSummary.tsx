import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';
import { STATUS, type KitStatus } from './tone';

/**
 * KPI kit status summary: how a set of measures stands, in one glance. Large
 * counts per status, a bar split in the same proportions, and the names of
 * the measures in the worst status, so the card says how many and which.
 *
 * Props: title, segments [{ key, label, count, status }] (worst first),
 * worst { label, items: [{ label, to }] }, footnote.
 */
export interface StatusSummaryProps {
  title: string;
  /** Worst first. */
  segments: { key: string; label: string; count: number; status: KitStatus }[];
  worst?: { label: string; items: { label: string; to?: string }[] } | null;
  footnote?: ReactNode;
  className?: string;
}

export default function StatusSummary({ title, segments, worst, footnote, className = '' }: StatusSummaryProps) {
  const total = segments.reduce((a, s) => a + s.count, 0) || 1;
  // Every status is shown, so the counts add up to the title; a neutral one (no target) only when it has members.
  const shown = segments.filter((s) => s.status !== 'neutral' || s.count);
  return (
    <section aria-label={title} className={`@container flex flex-col rounded-2xl border border-border bg-surface p-4 shadow-sm ${className}`}>
      <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted">{title}</p>
      <div className="mt-3 flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
        {segments.map((s) => (s.count ? <span key={s.key} className={(STATUS[s.status] ?? STATUS.neutral).fill} style={{ width: `${(s.count / total) * 100}%` }} /> : null))}
      </div>
      {/* Four counts sit in one row when the card has room and two by two when it does not (never three and one); three counts always share one row. */}
      <dl className={`mt-3 grid gap-x-3 gap-y-3 ${shown.length === 4 ? 'grid-cols-2 @[26rem]:grid-cols-4' : shown.length === 3 ? 'grid-cols-3' : 'grid-cols-2'}`}>
        {shown.map((s) => (
            // The term comes first in the markup (dl order); the count is drawn above it, top-aligned so every count sits on one line.
            <div key={s.key} className="flex min-w-0 flex-col">
              <dt className="order-2 mt-1 text-[11.5px] font-semibold leading-tight text-text-muted">{s.label}</dt>
              <dd className={`order-1 text-[28px] font-bold leading-none tabular-nums ${s.count ? (STATUS[s.status] ?? STATUS.neutral).text : 'text-text-subtle'}`}>{s.count}</dd>
            </div>
          ))}
      </dl>
      {worst && worst.items?.length > 0 && (
        <div className="mt-3 border-t border-border-subtle pt-2.5">
          <p className="text-[11px] font-semibold text-critical">{worst.label}</p>
          <ul className="mt-1 space-y-0.5">
            {worst.items.map((it) => (
              <li key={it.label} className="truncate text-[12px] leading-snug">
                {it.to ? (
                  <Link to={it.to} className="font-semibold text-text hover:text-brand hover:underline">
                    {it.label}
                  </Link>
                ) : (
                  <span className="font-semibold text-text">{it.label}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {footnote && <div className="mt-auto pt-3 text-[11px] leading-snug text-text-muted">{footnote}</div>}
    </section>
  );
}
