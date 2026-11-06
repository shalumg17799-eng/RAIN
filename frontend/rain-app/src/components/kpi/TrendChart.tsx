import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from 'react';
import { LineChart, Table2 } from 'lucide-react';
import { TREND_VAR, type TrendTone } from './tone';

/**
 * KPI kit trend chart: a line with a soft area, a dashed target line, the
 * latest value labelled, and a hover / focus readout of any point. The
 * one-line summary above it states the trend in words, and "View as table"
 * swaps the chart for its data (WCAG: the chart is never the only way in).
 * Drawn at its rendered width, so labels stay 11px however narrow the card.
 *
 * Props: points [{ label, value, n? }], format(v), target, targetLabel,
 * summary, tone ('improving' | 'worsening' | 'steady' | 'neutral'), height.
 */
function useWidth(fallback: number): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width) || fallback));
    ro.observe(el);
    return () => ro.disconnect();
  }, [fallback]);
  return [ref, w];
}

export interface TrendPoint {
  label: string;
  value: number;
  /** Sample size behind the value, shown in the table view. */
  n?: number | null;
}

export interface TrendChartProps {
  points: TrendPoint[];
  format: (v: number) => string;
  target?: number | null;
  targetLabel?: string;
  /** The trend in words, above the chart. */
  summary?: ReactNode;
  height?: number;
  tone?: TrendTone;
  tableCaption?: string;
}

export default function TrendChart({ points, format, target = null, targetLabel = '', summary, height = 200, tone = 'neutral', tableCaption = 'Trend' }: TrendChartProps) {
  const [asTable, setAsTable] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const id = useId();
  const gid = `tc${id.replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const [boxRef, measured] = useWidth(640);
  const W = Math.max(240, measured);
  const H = height;
  const pad = { l: 10, r: 14, t: 24, b: 28 };
  const vals = points.map((p) => p.value);
  const all = target != null ? [...vals, target] : vals;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const lo = min - span * 0.14;
  const hi = max + span * 0.14;
  const x = (i: number) => pad.l + (points.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (points.length - 1));
  const y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
  const areaPath = `${d} L${x(points.length - 1).toFixed(1)},${H - pad.b} L${x(0).toFixed(1)},${H - pad.b} Z`;
  const color = TREND_VAR[tone] ?? TREND_VAR.neutral;
  const last = points.length - 1;
  const endText = format(points[last].value);
  const showEnd = hover == null && endText.length * 7 < W * 0.35;
  const ticks = points.length > 8 ? [0, Math.floor(last / 2), last] : points.map((_, i) => i);
  const hasN = points.some((p) => p.n != null);

  const pick = (clientX: number, rect: DOMRect) => {
    const rel = ((clientX - rect.left) / rect.width) * W;
    const i = Math.round(((rel - pad.l) / (W - pad.l - pad.r)) * last);
    setHover(Math.max(0, Math.min(last, i)));
  };

  return (
    <div ref={boxRef}>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <p id={`${id}-sum`} className="max-w-2xl text-[12px] leading-relaxed text-text-muted">
          {summary}
        </p>
        <button
          type="button"
          onClick={() => setAsTable((v) => !v)}
          aria-pressed={asTable}
          className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-[11px] font-semibold text-text-muted hover:border-brand/40 hover:text-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
        >
          {asTable ? <LineChart className="h-3.5 w-3.5" aria-hidden="true" /> : <Table2 className="h-3.5 w-3.5" aria-hidden="true" />}
          {asTable ? 'View as chart' : 'View as table'}
        </button>
      </div>
      {asTable ? (
        <div className="max-w-full overflow-x-auto rounded-lg border border-border-subtle">
          <table className="w-full min-w-[260px] border-collapse text-left text-[12px]">
            <caption className="sr-only">{tableCaption}</caption>
            <thead className="bg-surface-2">
              <tr>
                <th scope="col" className="px-3 py-1.5 font-semibold text-text-muted">Period</th>
                <th scope="col" className="px-3 py-1.5 font-semibold text-text-muted">Value</th>
                {hasN && <th scope="col" className="px-3 py-1.5 font-semibold text-text-muted">Responses</th>}
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.label} className="border-t border-border-subtle">
                  <th scope="row" className="px-3 py-1.5 font-medium text-text">{p.label}</th>
                  <td className="px-3 py-1.5 tabular-nums text-text">{format(p.value)}</td>
                  {hasN && <td className="px-3 py-1.5 tabular-nums text-text">{p.n != null ? p.n.toLocaleString('en-US') : ''}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-auto w-full touch-none"
          role="img"
          aria-labelledby={`${id}-sum`}
          onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
          onPointerLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.16" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((f) => (
            <line key={f} x1={pad.l} x2={W - pad.r} y1={pad.t + f * (H - pad.t - pad.b)} y2={pad.t + f * (H - pad.t - pad.b)} stroke="var(--color-chart-grid)" strokeWidth="1" />
          ))}
          {target != null && (
            <g>
              <line x1={pad.l} x2={W - pad.r} y1={y(target)} y2={y(target)} stroke="var(--color-text-subtle)" strokeDasharray="5 4" strokeWidth="1.3" />
              <text x={pad.l + 2} y={y(target) - 5} textAnchor="start" fontSize="11" fill="var(--color-text-muted)">
                {targetLabel}
              </text>
            </g>
          )}
          <path d={areaPath} fill={`url(#${gid})`} />
          <path d={d} fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          {points.map((p, i) => (
            <circle key={p.label} cx={x(i)} cy={y(p.value)} r={i === last ? 3.8 : points.length <= 8 ? 2.6 : 0} fill={color} />
          ))}
          {ticks.map((i) => (
            <text key={i} x={x(i)} y={H - 8} textAnchor={i === 0 ? 'start' : i === last ? 'end' : 'middle'} fontSize="11" fill="var(--color-text-muted)">
              {points[i].label}
            </text>
          ))}
          {showEnd && (
            <text x={x(last) - 6} y={Math.max(13, y(points[last].value) - 9)} textAnchor="end" fontSize="12" fontWeight="700" fill="var(--color-text)" paintOrder="stroke" stroke="var(--color-surface)" strokeWidth="3">
              {endText}
            </text>
          )}
          {hover != null && (
            <g aria-hidden="true">
              <line x1={x(hover)} x2={x(hover)} y1={pad.t - 6} y2={H - pad.b} stroke="var(--color-border)" strokeWidth="1" />
              <circle cx={x(hover)} cy={y(points[hover].value)} r="4.5" fill="var(--color-surface)" stroke={color} strokeWidth="2" />
              {(() => {
                const label = `${points[hover].label}: ${format(points[hover].value)}`;
                const w = label.length * 6.6 + 14;
                const left = Math.min(Math.max(x(hover) - w / 2, 2), W - w - 2);
                return (
                  <g>
                    <rect x={left} y={2} width={w} height={20} rx="6" fill="var(--color-text)" />
                    <text x={left + w / 2} y={16} textAnchor="middle" fontSize="11.5" fontWeight="600" fill="var(--color-surface)">
                      {label}
                    </text>
                  </g>
                );
              })()}
            </g>
          )}
        </svg>
      )}
    </div>
  );
}
