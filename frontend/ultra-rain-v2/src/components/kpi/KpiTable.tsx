import { Link } from 'react-router-dom';
import { ArrowDownRight, ArrowRight, ArrowUpRight, CircleAlert, CircleCheck, CircleMinus, OctagonAlert } from 'lucide-react';
import { STATUS, TREND_TEXT, type KitStatus, type KitTrend } from './tone';

/**
 * KPI kit table: several measures compared at a glance, one row each, in
 * four aligned columns (Measure · Latest · Status · Change). Every cell is a
 * bold line over a muted line, and status and change are coloured text with
 * an icon rather than pills, so a list of five measures reads as a table and
 * not as a row of badges.
 *
 * Props: rows [{ key, name, to?, kind?, figure, words?, period?, status,
 * statusLabel, trend? }] where trend is { dir, tone, delta, vs, word };
 * caption (screen readers), className.
 */
const STATUS_ICON = { good: CircleCheck, warn: CircleAlert, bad: OctagonAlert, neutral: CircleMinus };
const ARROW = { up: ArrowUpRight, down: ArrowDownRight, flat: ArrowRight };

export interface KpiTableRow {
  key?: string;
  name: string;
  to?: string;
  kind?: string;
  figure: string;
  words?: string;
  period?: string;
  status: KitStatus;
  statusLabel: string;
  trend?: KitTrend | null;
}

export interface KpiTableProps {
  rows: KpiTableRow[];
  /** Read by screen readers. */
  caption?: string;
  className?: string;
}

export default function KpiTable({ rows, caption = 'Measures', className = '' }: KpiTableProps) {
  return (
    <div className={`max-w-full overflow-x-auto rounded-xl border border-border bg-surface ${className}`}>
      <table className="w-full min-w-[520px] border-collapse text-left">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border bg-surface-2/60 text-[10.5px] font-bold uppercase tracking-wider text-text-muted">
            <th scope="col" className="px-3 py-2 font-bold">Measure</th>
            <th scope="col" className="px-3 py-2 text-right font-bold">Latest</th>
            <th scope="col" className="px-3 py-2 font-bold">Status</th>
            <th scope="col" className="px-3 py-2 font-bold">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-subtle">
          {rows.map((r) => {
            const s = STATUS[r.status] ?? STATUS.neutral;
            const SIcon = STATUS_ICON[r.status] ?? CircleMinus;
            const t = r.trend && (r.trend.delta || r.trend.word !== 'No comparison yet') ? r.trend : null;
            const TIcon = t ? ARROW[t.dir] ?? ArrowRight : ArrowRight;
            return (
              <tr key={r.key ?? r.name} className="align-top">
                <th scope="row" className="px-3 py-2.5 font-normal">
                  {r.to ? (
                    <Link to={r.to} className="block text-[12.5px] font-semibold leading-snug text-text hover:text-brand hover:underline">
                      {r.name}
                    </Link>
                  ) : (
                    <span className="block text-[12.5px] font-semibold leading-snug text-text">{r.name}</span>
                  )}
                  {r.kind && <span className="mt-0.5 block text-[10.5px] text-text-muted">{r.kind}</span>}
                </th>
                <td className="whitespace-nowrap px-3 py-2.5 text-right">
                  <span className="block text-[15px] font-bold leading-tight tabular-nums text-text">{r.figure}</span>
                  <span className="mt-0.5 block text-[10.5px] text-text-muted">{[r.words, r.period].filter(Boolean).join(' · ')}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  <span className={`inline-flex items-center gap-1 text-[12px] font-semibold ${s.text}`}>
                    <SIcon className="h-3.5 w-3.5" aria-hidden="true" />
                    {r.statusLabel}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  {t ? (
                    <>
                      <span className={`inline-flex items-center gap-1 text-[12px] font-semibold tabular-nums ${TREND_TEXT[t.tone] ?? TREND_TEXT.steady}`}>
                        <TIcon className="h-3.5 w-3.5" aria-hidden="true" />
                        {t.delta || t.word}
                      </span>
                      <span className="mt-0.5 block text-[10.5px] text-text-muted">{[t.delta ? t.word : '', t.vs].filter(Boolean).join(' ')}</span>
                    </>
                  ) : (
                    <span className="text-[11.5px] text-text-subtle">No comparison yet</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
