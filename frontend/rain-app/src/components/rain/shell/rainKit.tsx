import type { ReactNode } from 'react';
import { Database } from 'lucide-react';

/**
 * The furniture every RAIN card and workbench shares, so the conversation and
 * the traditional screens read as one product: one card shell, the key points
 * under an answer, the data label every screen carries (spec: "Label
 * synthetic data on every screen"), pills, buttons, and a table that becomes
 * cards on a phone (spec: "tables become cards").
 */

export type Tone = 'good' | 'warning' | 'critical' | 'info' | 'neutral' | 'brand';

const TONE: Record<Tone, string> = {
  good: 'border-success/30 bg-success-subtle text-success-700',
  warning: 'border-warning/30 bg-warning-subtle text-warning-700',
  critical: 'border-critical/30 bg-critical-subtle text-critical-700',
  info: 'border-info/30 bg-info-subtle text-info-700',
  neutral: 'border-border bg-surface-2 text-text-muted',
  brand: 'border-brand/25 bg-brand/10 text-brand',
};

export function Pill({ tone = 'neutral', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold ${TONE[tone]} ${className}`}>{children}</span>;
}

/** Synthetic, public or aggregated: the label on every RAIN screen and card. */
export function DataLabel({ kind = 'Synthetic' }: { kind?: 'Synthetic' | 'Public + synthetic' | 'Aggregated, de-identified' | 'Public' }) {
  return (
    <span
      title="Synthetic data for a demo. Every organization and person shown is fictional."
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-dashed border-border bg-surface-2 px-2 py-0.5 text-[10.5px] font-semibold text-text-muted"
    >
      <Database className="h-3 w-3" aria-hidden="true" />
      {kind}
    </span>
  );
}

export function GroupLabel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`mb-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-text-subtle ${className}`}>{children}</p>;
}

/** The rest of the spec's answer, on the first card (house rule: one sentence in the bubble). */
export function KeyPoints({ points }: { points?: string[] }) {
  if (!points?.length) return null;
  return (
    <ul className="mb-3 space-y-1.5 rounded-xl bg-surface-2/70 px-3.5 py-2.5 text-[13px] leading-relaxed text-text">
      {points.map((p) => (
        <li key={p} className="flex gap-2">
          <span aria-hidden="true" className="mt-[7px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-brand" />
          <span>{p}</span>
        </li>
      ))}
    </ul>
  );
}

export function RainCard({
  eyebrow,
  title,
  points,
  aside,
  label = 'Synthetic',
  children,
  footer,
  className = '',
}: {
  eyebrow?: string;
  title?: ReactNode;
  points?: string[];
  aside?: ReactNode;
  label?: 'Synthetic' | 'Public + synthetic' | 'Aggregated, de-identified' | 'Public' | null;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`@container min-w-0 rounded-2xl border border-border bg-surface p-4 shadow-[0_1px_3px_rgba(0,0,0,0.04)] sm:p-5 ${className}`}>
      {(eyebrow || title || aside || label) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {eyebrow && <p className="text-[11px] font-bold uppercase tracking-[0.09em] text-brand">{eyebrow}</p>}
            {title && <h3 className="mt-0.5 text-[15px] font-semibold leading-snug text-text">{title}</h3>}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {aside}
            {label && <DataLabel kind={label} />}
          </div>
        </div>
      )}
      <KeyPoints points={points} />
      {children}
      {footer && <div className="mt-3 border-t border-border-subtle pt-3">{footer}</div>}
    </section>
  );
}

const BTN = {
  primary: 'bg-brand text-white hover:bg-brand/90',
  secondary: 'border border-border bg-surface text-text hover:bg-surface-2',
  ghost: 'text-brand hover:bg-brand/10',
};

export function Button({
  variant = 'secondary',
  onClick,
  disabled,
  children,
  title,
  className = '',
  type = 'button',
}: {
  variant?: keyof typeof BTN;
  onClick?: () => void;
  disabled?: boolean;
  children: ReactNode;
  title?: string;
  className?: string;
  type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50 ${BTN[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

/** A small segmented control for filters. */
export function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: Array<{ value: T; label: string }>; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label={label} className="inline-flex max-w-full flex-wrap gap-1 rounded-lg border border-border bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-[12px] font-semibold transition-colors ${value === o.value ? 'bg-surface text-brand shadow-sm' : 'text-text-muted hover:text-text'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** A labelled select, for workbench filters. */
export function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: Array<{ value: string; label: string }>; onChange: (v: string) => void }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-[11px] font-semibold text-text-subtle">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="min-h-[34px] min-w-0 rounded-lg border border-border bg-surface px-2 text-[13px] font-medium text-text">
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export interface Column<R> {
  key: string;
  label: string;
  align?: 'left' | 'right';
  render?: (row: R) => ReactNode;
  /** Hidden in the phone card view. */
  wideOnly?: boolean;
}

/**
 * A table when its container is 32rem or wider; narrower (a phone, the docked
 * Cockpit pane), each row is a card with its fields stacked, so nothing
 * scrolls sideways at 390 pixels.
 */
export function ResponsiveTable<R>({
  columns,
  rows,
  rowKey,
  caption,
  onRowClick,
  selectedKey,
  highlight = [],
  empty = 'Nothing to show.',
}: {
  columns: Column<R>[];
  rows: R[];
  rowKey: (r: R) => string;
  caption?: string;
  onRowClick?: (r: R) => void;
  selectedKey?: string | null;
  highlight?: string[];
  empty?: string;
}) {
  const value = (r: R, c: Column<R>) => (c.render ? c.render(r) : String((r as Record<string, unknown>)[c.key] ?? ''));
  if (!rows.length) return <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-[13px] text-text-muted">{empty}</p>;
  return (
    <div className="@container relative min-w-0">
      <div className="relative hidden overflow-x-auto rounded-xl border border-border @lg:block">
        <table className="w-full min-w-0 border-collapse text-left text-[13px]">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead className="bg-surface-2 text-[11.5px] uppercase tracking-wide text-text-subtle">
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={`px-3 py-2 font-semibold ${c.align === 'right' ? 'text-right' : ''}`}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const k = rowKey(r);
              const selected = selectedKey === k;
              const lit = highlight.includes(k);
              return (
                <tr
                  key={k}
                  onClick={onRowClick ? () => onRowClick(r) : undefined}
                  onKeyDown={onRowClick ? (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onRowClick(r)) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-selected={onRowClick ? selected : undefined}
                  className={`border-t border-border-subtle align-top ${onRowClick ? 'cursor-pointer hover:bg-surface-2/70 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand' : ''} ${selected ? 'bg-brand/[0.07]' : lit ? 'bg-warning-subtle/60' : ''}`}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={`px-3 py-2 text-text ${c.align === 'right' ? 'text-right tabular-nums' : ''}`}>
                      {value(r, c)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ul className="space-y-2 @lg:hidden" aria-label={caption}>
        {rows.map((r) => {
          const k = rowKey(r);
          const selected = selectedKey === k;
          const body = (
            <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-3 gap-y-1 text-[12.5px]">
              {columns
                .filter((c) => !c.wideOnly)
                .map((c) => (
                  <div key={c.key} className="contents">
                    <dt className="text-text-subtle">{c.label}</dt>
                    <dd className="min-w-0 break-words text-text">{value(r, c)}</dd>
                  </div>
                ))}
            </dl>
          );
          return (
            <li key={k}>
              {onRowClick ? (
                <button type="button" onClick={() => onRowClick(r)} aria-pressed={selected} className={`w-full rounded-xl border p-3 text-left ${selected ? 'border-brand bg-brand/[0.06]' : highlight.includes(k) ? 'border-warning/40 bg-warning-subtle/50' : 'border-border bg-surface'}`}>
                  {body}
                </button>
              ) : (
                <div className="rounded-xl border border-border bg-surface p-3">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export interface MeterSpan {
  from: number;
  to: number;
  /** A fill class from the tokens, e.g. "fill-brand" or "fill-critical/70". */
  className: string;
}

/**
 * A bar or set of bars on one track, drawn in SVG so widths come from the data
 * without inline styles. `max` is the scale; `markers` draw thin target ticks.
 */
export function Meter({ spans, markers = [], max = 100, className = 'h-2', label, track = true }: { spans: MeterSpan[]; markers?: number[]; max?: number; className?: string; label?: string; track?: boolean }) {
  return (
    <span className={`block w-full overflow-hidden rounded-full ${className}`}>
      <svg viewBox={`0 0 ${max} 10`} preserveAspectRatio="none" className="block h-full w-full" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
        {track && <rect x={0} y={0} width={max} height={10} className="fill-surface-2" />}
        {spans.map((sp, i) => (
          <rect key={i} x={Math.max(0, sp.from)} y={0} width={Math.max(0, Math.min(max, sp.to) - Math.max(0, sp.from))} height={10} className={sp.className} />
        ))}
        {markers.map((m, i) => (
          <rect key={`m${i}`} x={m - max * 0.005} y={0} width={max * 0.01} height={10} className="fill-text" />
        ))}
      </svg>
    </span>
  );
}

/** A thin horizontal bar against a scale, used inside tables and cards. */
export function Bar({ value, max, tone = 'brand', label }: { value: number; max: number; tone?: 'brand' | 'warning' | 'critical' | 'good' | 'muted'; label?: string }) {
  const fill = { brand: 'fill-brand', warning: 'fill-warning', critical: 'fill-critical', good: 'fill-success', muted: 'fill-text-subtle/50' }[tone];
  return <Meter spans={[{ from: 0, to: value, className: fill }]} max={max} className="h-2 min-w-[60px]" label={label} />;
}
