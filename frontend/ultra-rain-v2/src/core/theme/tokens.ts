/**
 * Theme token contract. A `BrandTheme` (on a market or client manifest) supplies
 * a partial set of token overrides; the ThemeProvider flattens it to CSS custom
 * properties and writes them on <html>. Everything not overridden falls back to
 * the defaults in index.css.
 */

/** Token overrides. Every field is optional — omit to inherit the default. */
export interface ThemeTokens {
  brand?: string;
  brandFg?: string;
  accent?: string;
  bg?: string;
  surface?: string;
  surface2?: string;
  border?: string;
  text?: string;
  textMuted?: string;
  textSubtle?: string;
  /** Categorical chart palette (chart-1..N). chart-1 defaults to the brand. */
  chart?: string[];
  confHigh?: string;
  confMed?: string;
  confLow?: string;
  /**
   * Semantic state colors. Normally left alone — the defaults in index.css are
   * right for most brands. Override when a brand's own palette would collide
   * with a state color and blunt its meaning: TrackLynk's coral brand sits close
   * to the default critical red, so the Oil & Gas market deepens `critical` to
   * keep "hazard" unmistakably distinct from ordinary brand chrome.
   */
  critical?: string;
  warning?: string;
  success?: string;
  info?: string;
}

export interface BrandTheme {
  light?: ThemeTokens;
  /** Font families (from the curated set). */
  fonts?: { sans?: string; display?: string };
}

/** token key → CSS custom property name (scalar tokens only; `chart` handled separately). */
const VAR_MAP: Record<Exclude<keyof ThemeTokens, 'chart'>, string> = {
  brand: '--color-brand',
  brandFg: '--color-brand-fg',
  accent: '--color-accent',
  bg: '--color-bg',
  surface: '--color-surface',
  surface2: '--color-surface-2',
  border: '--color-border',
  text: '--color-text',
  textMuted: '--color-text-muted',
  textSubtle: '--color-text-subtle',
  confHigh: '--color-conf-high',
  confMed: '--color-conf-med',
  confLow: '--color-conf-low',
  // The `-subtle` companions in index.css are color-mix()'d off these, so
  // overriding the base propagates to every tinted surface for free.
  critical: '--color-critical',
  warning: '--color-warning',
  success: '--color-success',
  info: '--color-info',
};

/** Every CSS var the ThemeProvider manages — cleared before each apply so a
 *  previous brand's overrides never linger when switching clients. */
export const MANAGED_VARS: string[] = [
  ...Object.values(VAR_MAP),
  ...Array.from({ length: 8 }, (_, i) => `--color-chart-${i + 1}`),
  '--font-sans',
  '--font-display',
];

/** Flatten a resolved ThemeTokens set to a { cssVar: value } map. */
export function tokensToVars(t: ThemeTokens): Record<string, string> {
  const out: Record<string, string> = {};
  (Object.keys(VAR_MAP) as Array<keyof typeof VAR_MAP>).forEach((k) => {
    const v = t[k];
    if (typeof v === 'string' && v) out[VAR_MAP[k]] = v;
  });
  if (t.chart) t.chart.forEach((c, i) => { if (c) out[`--color-chart-${i + 1}`] = c; });
  return out;
}
