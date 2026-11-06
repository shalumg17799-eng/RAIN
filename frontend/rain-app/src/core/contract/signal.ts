/**
 * The standard signal — a proactively surfaced insight (standard rule 7).
 *
 * The 35 legacy signal files use ~40 keys between them (`source`, `sources`,
 * `source_text`; `metric_text`, `metrics`; `affected_count`, `count`…). The
 * contract below is the one shape the backend sends; `normalizeSignal()` reads
 * any legacy record into it without editing the fixtures (safeguard 4).
 */
import { z } from 'zod';
import { toStatus, toConfidence, STATUSES } from './status';

export const signalSchema = z
  .object({
    id: z.string().min(1),
    title: z.string().min(1),
    /** One-line explanation under the title. */
    description: z.string().optional(),
    /** good · warning · critical · info · neutral */
    status: z.enum(STATUSES),
    /** Category id, e.g. `queue`, `fraud`, `churn`. */
    category: z.string().optional(),
    /** The headline figure as display text, e.g. "18 boarders · up from 6". */
    metricText: z.string().optional(),
    /** Count of members/accounts/people affected, when the signal has one. */
    affectedCount: z.number().optional(),
    /** Data-source ids or names that support the signal. */
    sources: z.array(z.string()).default([]),
    /** Display time, e.g. "8:42 AM" (fixed strings: the demo clock is fixed). */
    timestamp: z.string().optional(),
    /** Trend text, e.g. "+18% WoW". */
    trend: z.string().optional(),
    confidence: z.object({ score: z.number(), label: z.string().optional(), rationale: z.string().optional() }).optional(),
    /** Recommended next step as display text. */
    action: z.string().optional(),
    /** The persona's hero signal. */
    primary: z.boolean().optional(),
    /** True when the figures are illustrative rather than sourced. */
    illustrative: z.boolean().optional(),
  })
  .strict();

export type StandardSignal = z.infer<typeof signalSchema>;

type Legacy = Record<string, unknown>;

const str = (v: unknown): string | undefined => (typeof v === 'string' && v.trim() ? v : undefined);

/** Read one legacy signal record into the standard shape. Never throws. */
export function normalizeSignal(raw: Legacy): StandardSignal {
  const sources = Array.isArray(raw.sources)
    ? (raw.sources as unknown[]).filter((s): s is string => typeof s === 'string')
    : str(raw.source)
      ? [raw.source as string]
      : str(raw.source_text)
        ? [raw.source_text as string]
        : [];
  const affected = typeof raw.affected_count === 'number' ? raw.affected_count : typeof raw.count === 'number' ? raw.count : undefined;
  const confidence = toConfidence(raw.confidence) ?? undefined;
  const signal: StandardSignal = {
    id: String(raw.id ?? ''),
    title: String(raw.title ?? raw.summary ?? ''),
    description: str(raw.description) ?? str(raw.details),
    status: toStatus(raw.severity ?? raw.status ?? raw.impact, 'info'),
    category: str(raw.type) ?? str(raw.bucket),
    metricText: str(raw.metric_text),
    affectedCount: affected,
    sources,
    timestamp: str(raw.timestamp),
    trend: str(raw.trend),
    confidence,
    action: str(raw.action) ?? str(raw.actionShort),
    primary: typeof raw.primary === 'boolean' ? raw.primary : undefined,
    illustrative: typeof raw.illustrative === 'boolean' ? raw.illustrative : raw.real === false ? true : undefined,
  };
  // Drop undefined keys so the strict schema and JSON output stay clean.
  return Object.fromEntries(Object.entries(signal).filter(([, v]) => v !== undefined)) as StandardSignal;
}
