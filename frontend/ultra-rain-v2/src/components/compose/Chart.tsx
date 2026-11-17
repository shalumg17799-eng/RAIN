/**
 * Tier 3 chart: a line or bar chart described as data. Series colours come
 * from the chart tokens, so a compose chart wears each tenant's palette.
 */
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { toStatus } from '@core/contract/status';

export interface ChartSeries {
  name: string;
  points: Array<{ label: string; value: number }>;
}

export interface ChartProps {
  kind: 'line' | 'bar';
  series: ChartSeries[];
  unit?: string;
  title?: string;
  height?: number;
  /** A labelled horizontal reference line. */
  target?: { value: number; label?: string };
  /** The y-axis range; absent, recharts' default (from 0). */
  yMin?: number;
  yMax?: number;
  /** One colour per series, by design-token name. */
  colors?: string[];
  /** Bar charts: a status per point label, colouring that bar. */
  pointStatus?: Record<string, string>;
  /** Bar charts: stack the series. */
  stacked?: boolean;
}

const color = (i: number) => `var(--color-chart-${(i % 8) + 1})`;
const STATUS_FILL = { good: 'var(--color-success-600)', warning: 'var(--color-warning-500)', critical: 'var(--color-critical-600)', info: 'var(--color-info-600)', neutral: 'var(--color-text-subtle)' } as const;

export function Chart({ kind, series, unit = '', title, height = 220, target, yMin, yMax, colors, pointStatus, stacked }: ChartProps) {
  const seriesColor = (i: number) => (colors?.[i] ? `var(--color-${colors[i]})` : color(i));
  // Only set when asked for, so a chart without these options draws exactly as before.
  const domain = yMin != null || yMax != null ? { domain: [yMin ?? 'auto', yMax ?? 'auto'] as [number | 'auto', number | 'auto'] } : {};
  const reference = target ? <ReferenceLine y={target.value} stroke="var(--color-text-subtle)" strokeDasharray="5 4" label={target.label ? { value: target.label, position: 'insideTopLeft', fontSize: 11, fill: 'var(--color-text-muted)' } : undefined} /> : null;
  const labels = series[0]?.points.map((p) => p.label) ?? [];
  const data = labels.map((label, i) => Object.fromEntries([['label', label], ...series.map((s) => [s.name, s.points[i]?.value ?? null])]));
  const fmt = (v: number) => `${v}${unit}`;
  const axis = { stroke: 'var(--color-chart-axis)', fontSize: 11, tickLine: false };
  return (
    <figure className="rounded-xl border border-border bg-surface p-4">
      {title && <figcaption className="mb-2 text-[13px] font-semibold text-text">{title}</figcaption>}
      <div>
        <ResponsiveContainer width="100%" height={height}>
          {kind === 'bar' ? (
            <BarChart data={data}>
              <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
              <XAxis dataKey="label" {...axis} />
              <YAxis tickFormatter={fmt} {...axis} width={44} {...domain} />
              <Tooltip formatter={(v) => fmt(Number(v))} />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
              {reference}
              {series.map((s, i) => (
                <Bar key={s.name} dataKey={s.name} fill={seriesColor(i)} radius={stacked && i < series.length - 1 ? [0, 0, 0, 0] : [3, 3, 0, 0]} {...(stacked ? { stackId: 'stack' } : {})}>
                  {pointStatus && s.points.map((p) => <Cell key={p.label} fill={pointStatus[p.label] ? STATUS_FILL[toStatus(pointStatus[p.label])] : seriesColor(i)} />)}
                </Bar>
              ))}
            </BarChart>
          ) : (
            <LineChart data={data}>
              <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
              <XAxis dataKey="label" {...axis} />
              <YAxis tickFormatter={fmt} {...axis} width={44} {...domain} />
              <Tooltip formatter={(v) => fmt(Number(v))} />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
              {reference}
              {series.map((s, i) => <Line key={s.name} type="monotone" dataKey={s.name} stroke={seriesColor(i)} strokeWidth={2} dot={false} />)}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
