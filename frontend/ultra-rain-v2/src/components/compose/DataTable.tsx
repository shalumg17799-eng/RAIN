/** Tier 3 table: columns and rows as data. Status columns draw as StatusBadge. */
import StatusBadge from '../common/StatusBadge';
import type { ReactNode } from 'react';
import { toStatus } from '@core/contract/status';

export interface DataTableColumn {
  key: string;
  label: string;
  align?: 'left' | 'right';
  /** `status` draws the cell as a StatusBadge; `bar` adds a bar filled to the value (of `max`, default 100). */
  kind?: 'text' | 'number' | 'status' | 'bar';
  /** A second, smaller line under the cell, from this row field. */
  subKey?: string;
  /** Colours the cell by the status word in this row field. On a `status` column, the badge keeps the cell's own word and takes this colour. */
  toneKey?: string;
  /** `bar` columns: the value that fills the bar. */
  max?: number;
}

export interface DataTableProps {
  columns: DataTableColumn[];
  rows: Array<Record<string, string | number | null>>;
  caption?: string;
  /** Rows become stacked cards when the container is narrower than 32rem. Optional; absent, nothing changes. */
  stack?: boolean;
  /** Row indexes drawn emphasised (the recommended option). */
  highlightRows?: number[];
}

const TONE_TEXT = { good: 'text-success-700', warning: 'text-warning-700', critical: 'text-critical-700', info: 'text-info-700', neutral: 'text-text-muted' } as const;

/** One cell, with the optional bar, tone and second line. Plain cells render exactly as before. */
function Cell({ c, row }: { c: DataTableColumn; row: Record<string, string | number | null> }) {
  const v = row[c.key];
  const toneWord = c.toneKey ? row[c.toneKey] : null;
  if (c.kind === 'status' && v != null && toneWord != null) {
    const badge = <StatusBadge status={toneWord} label={String(v)} />;
    return c.subKey && row[c.subKey] != null && row[c.subKey] !== '' ? <>{badge}<span className="mt-0.5 block text-[11px] text-text-subtle">{row[c.subKey]}</span></> : badge;
  }
  const tone = toneWord != null ? TONE_TEXT[toStatus(toneWord)] : null;
  let main: ReactNode = c.kind === 'status' && v != null ? <StatusBadge status={v} /> : v ?? '—';
  if (c.kind === 'bar' && typeof v === 'number') {
    const pct = Math.max(0, Math.min(100, (v / (c.max ?? 100)) * 100));
    main = (
      <span className="inline-flex min-w-[96px] items-center gap-2">
        <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
          <span className="block h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
        </span>
        <span className="tabular-nums">{v.toLocaleString('en-US')}</span>
      </span>
    );
  }
  if (tone) main = <span className={`font-semibold ${tone}`}>{main}</span>;
  if (c.subKey && row[c.subKey] != null && row[c.subKey] !== '') main = <>{main}<span className="mt-0.5 block text-[11px] text-text-subtle">{row[c.subKey]}</span></>;
  return main;
}

const plain = (c: DataTableColumn) => !c.subKey && !c.toneKey && c.kind !== 'bar';

export function DataTable({ columns, rows, caption, stack, highlightRows }: DataTableProps) {
  if (stack) return <StackedTable columns={columns} rows={rows} caption={caption} highlightRows={highlightRows} />;
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-left text-[12.5px]">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-border bg-surface-2">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-text-muted ${c.align === 'right' || c.kind === 'number' ? 'text-right' : ''}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={highlightRows?.includes(i) ? 'border-b border-border-subtle bg-brand/[0.06] font-semibold last:border-0' : 'border-b border-border-subtle last:border-0'}>
              {columns.map((c) => {
                const v = row[c.key];
                return (
                  <td key={c.key} className={`px-3 py-2 text-text ${c.align === 'right' || c.kind === 'number' ? 'text-right tabular-nums' : ''}`}>
                    {plain(c) ? (c.kind === 'status' && v != null ? <StatusBadge status={v} /> : v ?? '—') : <Cell c={c} row={row} />}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The `stack` variant: the same table from 32rem up; narrower, one card per row. */
function StackedTable({ columns, rows, caption, highlightRows }: Omit<DataTableProps, 'stack'>) {
  const cell = (c: DataTableColumn, row: Record<string, string | number | null>) => {
    if (!plain(c)) return <Cell c={c} row={row} />;
    const v = row[c.key];
    return c.kind === 'status' && v != null ? <StatusBadge status={v} /> : v ?? '—';
  };
  return (
    <div className="@container relative min-w-0">
      <div className="hidden @lg:block">
        <DataTable columns={columns} rows={rows} caption={caption} highlightRows={highlightRows} />
      </div>
      <ul className="space-y-2 @lg:hidden" aria-label={caption}>
        {rows.map((row, i) => (
          <li key={i} className={highlightRows?.includes(i) ? 'rounded-xl border border-brand/40 bg-brand/[0.06] p-3 font-semibold' : 'rounded-xl border border-border bg-surface p-3'}>
            <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-1 text-[12.5px]">
              {columns.map((c) => (
                <div key={c.key} className="contents">
                  <dt className="text-text-subtle">{c.label}</dt>
                  <dd className="min-w-0 break-words text-text">{cell(c, row)}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
