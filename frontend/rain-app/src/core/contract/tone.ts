/**
 * Icon tones for KPI tiles (standard rule 6: no display details in data).
 *
 * A tile says what its figure *is* — a status, the brand, or one of four
 * neutral categories — and the frontend decides the colour. The backend sends
 * `iconTone: 'warning'`, never `'text-amber-600'`.
 */
import type { Status } from './status';

/** The five statuses, the brand, and four category accents that carry no status. */
export type IconTone = Status | 'brand' | 'category1' | 'category2' | 'category3' | 'category4';

export const ICON_TONES: readonly IconTone[] = [
  'good', 'warning', 'critical', 'info', 'neutral', 'brand', 'category1', 'category2', 'category3', 'category4',
];

/** Tone → the icon's colour and its tile square, from tokens. */
export const ICON_TONE_STYLE: Record<IconTone, { color: string; bg: string }> = {
  good: { color: 'text-success-600', bg: 'bg-success-500/10' },
  warning: { color: 'text-warning-600', bg: 'bg-warning-500/10' },
  critical: { color: 'text-critical-600', bg: 'bg-critical-500/10' },
  info: { color: 'text-info-600', bg: 'bg-info-500/10' },
  neutral: { color: 'text-text-muted', bg: 'bg-text-muted/10' },
  brand: { color: 'text-brand', bg: 'bg-brand/10' },
  category1: { color: 'text-violet-600', bg: 'bg-violet-500/10' },
  category2: { color: 'text-cyan-600', bg: 'bg-cyan-500/10' },
  category3: { color: 'text-teal-700', bg: 'bg-teal-500/10' },
  category4: { color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
};

/** A tile's icon classes; an unknown or missing tone draws neutral. */
export function tileIcon(tile: { iconTone?: string }): { color: string; bg: string } {
  return ICON_TONE_STYLE[(tile.iconTone as IconTone) in ICON_TONE_STYLE ? (tile.iconTone as IconTone) : 'neutral'];
}
