/**
 * KPI kit: the shared vocabulary of status and trend, in design tokens only.
 *
 * A status says where a number stands against its target (good, warn, bad,
 * neutral). A trend says whether it is getting better or worse for the
 * organisation, not which way the line points: a rising complaint count is
 * "worsening" and red. Callers decide both; the kit only draws them, always
 * with a word beside the colour (WCAG 1.4.1).
 */

/** Where a number stands against its target. */
export type KitStatus = 'good' | 'warn' | 'bad' | 'neutral';
/** Whether a measure is getting better or worse for the organisation (`inverse`: drawn on a brand surface). */
export type TrendTone = 'improving' | 'worsening' | 'steady' | 'neutral' | 'inverse';

/** A measure's change, as the badges and table draw it: which way, what it means, by how much, against what. */
export interface KitTrend {
  dir: 'up' | 'down' | 'flat';
  tone: TrendTone;
  delta?: string;
  word?: string;
  vs?: string;
}

interface StatusStyle { badge: string; text: string; fill: string; edge: string }

/** Status → badge surface, text colour, solid fill (bars, edges). */
export const STATUS: Record<KitStatus, StatusStyle> = {
  good: { badge: 'border-success/40 bg-success/[0.07] text-success', text: 'text-success', fill: 'bg-success', edge: 'before:bg-success' },
  warn: { badge: 'border-warning/45 bg-warning/[0.08] text-warning', text: 'text-warning', fill: 'bg-warning', edge: 'before:bg-warning' },
  bad: { badge: 'border-critical/45 bg-critical/[0.07] text-critical', text: 'text-critical', fill: 'bg-critical', edge: 'before:bg-critical' },
  neutral: { badge: 'border-border bg-surface-2 text-text-muted', text: 'text-text-muted', fill: 'bg-text-subtle', edge: 'before:bg-border' },
};

/** Trend tone → text colour (also a chart's `currentColor`). */
export const TREND_TEXT: Record<TrendTone, string> = {
  improving: 'text-success',
  worsening: 'text-critical',
  steady: 'text-text-muted',
  neutral: 'text-brand',
  inverse: 'text-white',
};

/** Trend tone → pill surface. */
export const TREND_PILL: Record<Exclude<TrendTone, 'inverse'>, string> = {
  improving: 'border-success/40 bg-success/[0.07] text-success',
  worsening: 'border-critical/45 bg-critical/[0.07] text-critical',
  steady: 'border-border bg-surface-2 text-text-muted',
  neutral: 'border-brand/30 bg-brand/[0.05] text-brand',
};

/** On an inverse (brand) surface. */
export const TREND_PILL_INVERSE = 'border-white/25 bg-white/[0.12] text-white';

/** A trend tone's CSS colour, for SVG strokes and fills. */
export const TREND_VAR: Record<TrendTone, string> = {
  improving: 'var(--color-success)',
  worsening: 'var(--color-critical)',
  steady: 'var(--color-text-muted)',
  neutral: 'var(--color-brand)',
  inverse: 'var(--color-text-inverse)',
};

/** A status's CSS colour, for SVG. */
export const STATUS_VAR: Record<KitStatus, string> = {
  good: 'var(--color-success)',
  warn: 'var(--color-warning)',
  bad: 'var(--color-critical)',
  neutral: 'var(--color-text-subtle)',
};

/**
 * The tone of a plain series with a known good direction: its last value
 * against its first, with a small dead band so noise reads as steady.
 */
export function toneOfSeries(values: readonly (number | null | undefined)[] | null | undefined, higherIsBetter: boolean): TrendTone {
  const pts = (values ?? []).filter((v): v is number => v != null);
  if (pts.length < 2) return 'steady';
  const d = pts[pts.length - 1] - pts[0];
  if (d === 0 || Math.abs(d) < Math.abs(pts[0]) * 0.005) return 'steady';
  return d > 0 === higherIsBetter ? 'improving' : 'worsening';
}
