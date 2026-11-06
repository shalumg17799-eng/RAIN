/**
 * Props schemas for every catalog type. Written once, used three ways: the
 * renderer validates incoming props, the contract tests validate the examples,
 * and `npm run catalog` exports them as JSON Schema for the backend.
 */
import { z } from 'zod';
import { ICON_TONES, type IconTone } from '../contract/tone';
import { ICONS } from '../contract/icons';
import { STATUSES } from '../contract/status';
import { signalSchema } from '../contract/signal';
import { componentSpecSchema } from '../contract/aiTurn';

const status = z.enum(STATUSES);
const trendTone = z.enum(['improving', 'worsening', 'steady', 'neutral']);

/** The KPI kit's trend badge: direction, what the move means, and words. */
export const kitTrend = z.object({
  dir: z.enum(['up', 'down', 'flat']),
  tone: trendTone,
  delta: z.string().optional(),
  vs: z.string().optional(),
  word: z.string().optional(),
});

export const standardTrend = z.object({
  direction: z.enum(['up', 'down', 'flat']),
  value: z.number().optional(),
  label: z.string().optional(),
  good: z.boolean().optional(),
});

/** How a number is printed, in place of a format function. */
export const valueFormat = z.object({
  prefix: z.string().optional(),
  suffix: z.string().optional(),
  decimals: z.number().int().min(0).max(4).optional(),
});

// ── Tier 2 ────────────────────────────────────────────────────────────

export const signalCardProps = z.object({
  signal: signalSchema,
  tone: z.enum(['urgent', 'calm']).optional(),
  compact: z.boolean().optional(),
  showAction: z.boolean().optional(),
});

export const actionCardsProps = z.object({
  actions: z.array(z.object({
    id: z.string(),
    title: z.string(),
    description: z.string().optional(),
    system: z.string().optional(),
    confidence: z.number().optional(),
    impact: z.string().optional(),
  }).loose()).min(1),
  confirmLabel: z.string().optional(),
});

export const metricCardProps = z.object({
  title: z.string(),
  figure: z.string(),
  words: z.string().optional(),
  period: z.string().optional(),
  eyebrow: z.string().optional(),
  status: status.optional(),
  statusLabel: z.string().optional(),
  trend: kitTrend.optional(),
  series: z.array(z.number()).optional(),
  target: z.number().nullable().optional(),
  footnote: z.string().optional(),
  size: z.enum(['sm', 'md']).optional(),
});

export const trendChartProps = z.object({
  points: z.array(z.object({ label: z.string(), value: z.number(), n: z.number().optional() })).min(2),
  format: valueFormat.optional(),
  target: z.number().nullable().optional(),
  targetLabel: z.string().optional(),
  summary: z.string().optional(),
  tone: trendTone.optional(),
  height: z.number().optional(),
  tableCaption: z.string().optional(),
});

export const targetBarProps = z.object({
  value: z.number(),
  target: z.number().nullable().optional(),
  min: z.number().optional(),
  max: z.number().optional(),
  percent: z.boolean().optional(),
  status: status.optional(),
  valueLabel: z.string().optional(),
  targetLabel: z.string().optional(),
  compact: z.boolean().optional(),
});

export const peerBarProps = z.object({
  value: z.number(),
  peer: z.number().nullable().optional(),
  min: z.number().optional(),
  max: z.number().optional(),
  higherIsBetter: z.boolean().optional(),
  valueLabel: z.string().optional(),
});

export const statusSummaryProps = z.object({
  title: z.string(),
  segments: z.array(z.object({ key: z.string(), label: z.string(), count: z.number(), status })),
  worst: z.object({ label: z.string(), items: z.array(z.object({ label: z.string() })) }).optional(),
  footnote: z.string().optional(),
});

export const kpiTableProps = z.object({
  rows: z.array(z.object({
    key: z.string(),
    name: z.string(),
    kind: z.string().optional(),
    figure: z.string(),
    words: z.string().optional(),
    period: z.string().optional(),
    status,
    statusLabel: z.string(),
    trend: kitTrend.optional(),
  })).min(1),
  caption: z.string().optional(),
});

// ── Tier 3 ────────────────────────────────────────────────────────────

/** A row of KPI tiles: what each figure is (a status, the brand or a category), never its colour. */
export const statTilesProps = z.object({
  stats: z.array(z.object({
    id: z.string(),
    label: z.string(),
    value: z.string(),
    trend: z.string().optional(),
    positive: z.boolean().optional(),
    icon: z.enum(Object.keys(ICONS) as [string, ...string[]]).optional(),
    iconTone: z.enum(ICON_TONES as [IconTone, ...IconTone[]]).optional(),
    chipText: z.string().nullable().optional(),
    tone: z.enum(['neutral']).optional(),
  })).min(1),
});

/** The one number to look at first, on the brand surface. */
export const heroMetricProps = z.object({
  title: z.string(),
  figure: z.string(),
  eyebrow: z.string().optional(),
  words: z.string().optional(),
  period: z.string().optional(),
  status: status.optional(),
  statusLabel: z.string().optional(),
  trend: kitTrend.optional(),
  why: z.string().optional(),
  detail: z.string().optional(),
  series: z.array(z.number()).optional(),
  target: z.number().nullable().optional(),
  seriesFrom: z.string().optional(),
  seriesTo: z.string().optional(),
});

/** A half-donut score gauge, 0–100, coloured by state. */
export const gaugeProps = z.object({
  score: z.number().min(0).max(100),
  status,
  size: z.number().optional(),
});

/** One signal as a compact tile (the briefing's top-insights row). */
export const signalTileProps = z.object({ signal: signalSchema });

/** How work runs today, step by step, and where the product intervenes. */
export const currentStateProps = z.object({
  data: z.object({
    title: z.string(),
    subtitle: z.string().optional(),
    illustrative: z.boolean().optional(),
    cycleTimeNote: z.string().optional(),
    steps: z.array(z.object({ id: z.string(), label: z.string(), detail: z.string().optional(), state: z.string(), system: z.string().optional(), isDecision: z.boolean().optional() })).min(1),
    gapSummary: z.string().optional(),
    interventions: z.array(z.object({
      id: z.string(), stepId: z.string(), currentStep: z.string().optional(), intervention: z.string(), capability: z.string().optional(), impact: z.string().optional(),
    })),
  }),
  productName: z.string().optional(),
  gapLegend: z.string().optional(),
});

/** A persona's journey: phases with emotion, pain points and the opportunity, traced to signals. */
export const journeyMapProps = z.object({
  data: z.object({
    scenario: z.string(),
    timeframe: z.string(),
    baselineSatisfaction: z.number(),
    baselineNote: z.string(),
    illustrative: z.boolean().optional(),
    phases: z.array(z.object({
      id: z.string(), index: z.number(), name: z.string(), emotion: z.number(), emotionLabel: z.string(),
      touchpoints: z.array(z.string()), action: z.string(), thought: z.string(),
      painPoints: z.array(z.string()), opportunity: z.string(), momentOfTruth: z.boolean().optional(),
      momentLabel: z.string().optional(), demoStep: z.string().optional(), flowKey: z.string().optional(),
    })).min(1),
    traceability: z.array(z.object({ phase: z.string(), painPoint: z.string(), signal: z.string(), signalId: z.string().optional(), demoStep: z.string().optional() })).optional(),
  }),
  title: z.string().optional(),
  idleHint: z.string().optional(),
});

const children = z.array(componentSpecSchema).min(1);
const gap = z.enum(['sm', 'md', 'lg']);

export const stackProps = z.object({ children, gap: gap.optional() });
export const gridProps = z.object({ children, columns: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4)]).optional(), gap: gap.optional() });
export const textProps = z.object({ text: z.string(), tone: z.enum(['default', 'muted']).optional(), size: z.enum(['sm', 'md']).optional() });
export const calloutProps = z.object({ title: z.string(), body: z.string().optional(), status: status.optional() });
export const statProps = z.object({
  label: z.string(),
  value: z.string(),
  caption: z.string().optional(),
  status: status.optional(),
  trend: standardTrend.optional(),
  icon: z.string().optional(),
});
export const dataTableProps = z.object({
  columns: z.array(z.object({
    key: z.string(),
    label: z.string(),
    align: z.enum(['left', 'right']).optional(),
    kind: z.enum(['text', 'number', 'status']).optional(),
  })).min(1),
  rows: z.array(z.record(z.string(), z.union([z.string(), z.number(), z.null()]))),
  caption: z.string().optional(),
  /**
   * Optional. When true, each row becomes a stacked card wherever the table's
   * container is narrower than 32rem (a phone, a docked side pane). Added for
   * RAIN, whose answers run in a 380-pixel pane and must work at 390 pixels
   * with no sideways scroll. Absent, the table renders exactly as before.
   */
  stack: z.boolean().optional(),
});
export const chartProps = z.object({
  kind: z.enum(['line', 'bar']),
  series: z.array(z.object({ name: z.string(), points: z.array(z.object({ label: z.string(), value: z.number() })).min(1) })).min(1),
  unit: z.string().optional(),
  title: z.string().optional(),
  height: z.number().optional(),
});
export const statusBadgeProps = z.object({ status: z.union([z.string(), z.number()]), label: z.string().optional(), size: z.enum(['sm', 'lg']).optional() });
export const sparklineProps = z.object({
  values: z.array(z.number()).min(2),
  target: z.number().nullable().optional(),
  tone: trendTone.optional(),
  width: z.number().optional(),
  height: z.number().optional(),
});
export const confidenceBadgeProps = z.object({ score: z.number(), note: z.string().optional() });
export const illustrativeNoteProps = z.object({ note: z.string().optional(), size: z.enum(['sm', 'md']).optional() });
