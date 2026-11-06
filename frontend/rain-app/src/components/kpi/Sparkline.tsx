import { useId } from 'react';
import { TREND_VAR, type TrendTone } from './tone';

/**
 * KPI kit sparkline: a small trend line coloured by what the move means
 * (`tone`), with an optional target line and a soft area under the line.
 * Decorative: the card around it states the values in words.
 */
export interface SparklineProps {
  values: readonly (number | null | undefined)[] | null | undefined;
  width?: number;
  height?: number;
  target?: number | null;
  tone?: TrendTone;
  area?: boolean;
  className?: string;
}

export default function Sparkline({ values, width = 132, height = 34, target = null, tone, area = true, className = '' }: SparklineProps) {
  // useId() contains colons, which url(#…) references do not accept.
  const gid = `spk${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const pts = (values ?? []).filter((v): v is number => v != null);
  if (pts.length < 2) return null;
  const all = target != null ? [...pts, target] : pts;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const inset = 3.5;
  const step = (width - inset * 2) / (pts.length - 1);
  const x = (i: number) => inset + i * step;
  const y = (v: number) => height - inset - ((v - min) / span) * (height - inset * 2);
  const d = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const fillPath = `${d} L${x(pts.length - 1).toFixed(1)},${height} L${x(0).toFixed(1)},${height} Z`;
  const color = (tone && TREND_VAR[tone]) ?? 'var(--color-brand)';
  const targetStroke = tone === 'inverse' ? 'rgba(255,255,255,0.55)' : 'var(--color-text-subtle)';
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} className={`block h-auto max-w-full ${className}`} aria-hidden="true">
      {area && (
        <>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={tone === 'inverse' ? 0.28 : 0.18} />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={fillPath} fill={`url(#${gid})`} />
        </>
      )}
      {target != null && <line x1={inset} x2={width - inset} y1={y(target)} y2={y(target)} stroke={targetStroke} strokeDasharray="3 3" strokeWidth="1" />}
      <path d={d} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1])} r="2.6" fill={color} />
    </svg>
  );
}
