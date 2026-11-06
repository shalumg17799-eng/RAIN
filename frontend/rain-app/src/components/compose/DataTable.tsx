/** Tier 3 table: columns and rows as data. Status columns draw as StatusBadge. */
import StatusBadge from '../common/StatusBadge';

export interface DataTableColumn {
  key: string;
  label: string;
  align?: 'left' | 'right';
  /** `status` draws the cell as a StatusBadge. */
  kind?: 'text' | 'number' | 'status';
}

export interface DataTableProps {
  columns: DataTableColumn[];
  rows: Array<Record<string, string | number | null>>;
  caption?: string;
  /** Rows become stacked cards when the container is narrower than 32rem. Optional; absent, nothing changes. */
  stack?: boolean;
}

export function DataTable({ columns, rows, caption, stack }: DataTableProps) {
  if (stack) return <StackedTable columns={columns} rows={rows} caption={caption} />;
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
            <tr key={i} className="border-b border-border-subtle last:border-0">
              {columns.map((c) => {
                const v = row[c.key];
                return (
                  <td key={c.key} className={`px-3 py-2 text-text ${c.align === 'right' || c.kind === 'number' ? 'text-right tabular-nums' : ''}`}>
                    {c.kind === 'status' && v != null ? <StatusBadge status={v} /> : v ?? '—'}
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
function StackedTable({ columns, rows, caption }: Omit<DataTableProps, 'stack'>) {
  const cell = (c: DataTableColumn, v: string | number | null | undefined) => (c.kind === 'status' && v != null ? <StatusBadge status={v} /> : v ?? '–');
  return (
    <div className="@container relative min-w-0">
      <div className="hidden @lg:block">
        <DataTable columns={columns} rows={rows} caption={caption} />
      </div>
      <ul className="space-y-2 @lg:hidden" aria-label={caption}>
        {rows.map((row, i) => (
          <li key={i} className="rounded-xl border border-border bg-surface p-3">
            <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-1 text-[12.5px]">
              {columns.map((c) => (
                <div key={c.key} className="contents">
                  <dt className="text-text-subtle">{c.label}</dt>
                  <dd className="min-w-0 break-words text-text">{cell(c, row[c.key])}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
