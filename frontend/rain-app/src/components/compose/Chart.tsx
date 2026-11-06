/**
 * Tier 3 chart: a line or bar chart described as data. Series colours come
 * from the chart tokens, so a compose chart wears each tenant's palette.
 */
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

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
}

const color = (i: number) => `var(--color-chart-${(i % 8) + 1})`;

export function Chart({ kind, series, unit = '', title, height = 220 }: ChartProps) {
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
              <YAxis tickFormatter={fmt} {...axis} width={44} />
              <Tooltip formatter={(v) => fmt(Number(v))} />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
              {series.map((s, i) => <Bar key={s.name} dataKey={s.name} fill={color(i)} radius={[3, 3, 0, 0]} />)}
            </BarChart>
          ) : (
            <LineChart data={data}>
              <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
              <XAxis dataKey="label" {...axis} />
              <YAxis tickFormatter={fmt} {...axis} width={44} />
              <Tooltip formatter={(v) => fmt(Number(v))} />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
              {series.map((s, i) => <Line key={s.name} type="monotone" dataKey={s.name} stroke={color(i)} strokeWidth={2} dot={false} />)}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
