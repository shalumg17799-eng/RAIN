/**
 * The one status vocabulary (standard rule 7).
 *
 * Every state the backend sends and every state a component draws is one of
 * five values. The fixtures spell "fine" as good, ok, healthy, online, pass,
 * compliant, validated, connected, green, g… — `toStatus()` maps all of them,
 * so legacy data keeps working while new data uses the five words.
 *
 * Colour is decided here, from tokens, never by the data (rule 6).
 */

export const STATUSES = ['good', 'warning', 'critical', 'info', 'neutral'] as const;
export type Status = (typeof STATUSES)[number];

/** Legacy spellings → the standard five. Keys are lower-case, trimmed. */
const ALIASES: Record<string, Status> = {
  // good
  good: 'good', ok: 'good', okay: 'good', healthy: 'good', online: 'good', pass: 'good', passed: 'good',
  compliant: 'good', validated: 'good', valid: 'good', connected: 'good', green: 'good', g: 'good',
  success: 'good', complete: 'good', completed: 'good', done: 'good', met: 'good', normal: 'good',
  stable: 'good', ready: 'good', approved: 'good', resolved: 'good', recovered: 'good', 'on_time': 'good',
  'on-time': 'good', 'on time': 'good', delivered: 'good', 'auto-fixed': 'good', confirmed: 'good',
  'well capitalized': 'good', low: 'good', best: 'good', 'on-post': 'good', current: 'good', exists: 'good',
  'on_file': 'good', positive: 'good',
  // warning
  warning: 'warning', warn: 'warning', amber: 'warning', a: 'warning', yellow: 'warning', partial: 'warning',
  degraded: 'warning', 'at_risk': 'warning', 'at risk': 'warning', 'at-risk': 'warning', watch: 'warning',
  attention: 'warning', medium: 'warning', moderate: 'warning', pending: 'warning', review: 'warning',
  'under review': 'warning', 'under_review': 'warning', 'pending review': 'warning', behind: 'warning',
  below: 'warning', 'near_threshold': 'warning', late: 'warning', gap: 'warning', deviation: 'warning',
  recovering: 'warning', syncing: 'warning', monitoring: 'warning', monitored: 'warning', flag: 'warning',
  escalated: 'warning', 'awaiting approval': 'warning', 'access needed': 'warning', mid: 'warning',
  // critical
  critical: 'critical', bad: 'critical', red: 'critical', r: 'critical', error: 'critical', failed: 'critical',
  failing: 'critical', fail: 'critical', breached: 'critical', alarm: 'critical', down: 'critical',
  disconnected: 'critical', expired: 'critical', high: 'critical', highest: 'critical', severe: 'critical',
  'past_due': 'critical', 'past due': 'critical', overdue: 'critical', missing: 'critical', risk: 'critical',
  'fails_80': 'critical', negative: 'critical',
  // info
  info: 'info', information: 'info', informational: 'info', 'in progress': 'info', 'in_progress': 'info',
  active: 'info', running: 'info', scheduled: 'info', upcoming: 'info', staged: 'info', open: 'info',
  drill: 'info', primary: 'info', action: 'info', progress: 'info', policy: 'info',
  // neutral
  neutral: 'neutral', muted: 'neutral', unknown: 'neutral', none: 'neutral', 'n/a': 'neutral', closed: 'neutral',
  'not_started': 'neutral', 'not started': 'neutral', 'not collected': 'neutral', 'no target yet': 'neutral',
  logged: 'neutral', audited: 'neutral', overridden: 'neutral',
};

/**
 * Map any legacy state value onto the standard vocabulary. Unknown values are
 * `neutral` (never an alarm by accident). Numbers are read as a 0–100 health
 * score: ≥ 80 good, ≥ 60 warning, otherwise critical.
 */
export function toStatus(value: unknown, fallback: Status = 'neutral'): Status {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value >= 80) return 'good';
    if (value >= 60) return 'warning';
    return 'critical';
  }
  if (typeof value !== 'string') return fallback;
  const key = value.trim().toLowerCase();
  if ((STATUSES as readonly string[]).includes(key)) return key as Status;
  return ALIASES[key] ?? fallback;
}

/** Token-based classes for each status. The only place status becomes colour. */
export const STATUS_STYLE: Record<Status, { text: string; bg: string; border: string; dot: string; label: string }> = {
  good: { text: 'text-success', bg: 'bg-success-subtle', border: 'border-success/30', dot: 'bg-success', label: 'Good' },
  warning: { text: 'text-warning', bg: 'bg-warning-subtle', border: 'border-warning/30', dot: 'bg-warning', label: 'Watch' },
  critical: { text: 'text-critical', bg: 'bg-critical-subtle', border: 'border-critical/30', dot: 'bg-critical', label: 'Critical' },
  info: { text: 'text-info', bg: 'bg-info-subtle', border: 'border-info/30', dot: 'bg-info', label: 'Info' },
  neutral: { text: 'text-text-muted', bg: 'bg-bg', border: 'border-border', dot: 'bg-text-subtle', label: 'Neutral' },
};

/** CSS custom property for a status colour, for charts and inline SVG. */
export function statusColorVar(status: Status): string {
  return {
    good: 'var(--color-success)',
    warning: 'var(--color-warning)',
    critical: 'var(--color-critical)',
    info: 'var(--color-info)',
    neutral: 'var(--color-text-subtle)',
  }[status];
}

/** The standard trend shape (rule 7). */
export interface Trend {
  direction: 'up' | 'down' | 'flat';
  value?: number;
  label?: string;
  /** Whether this direction is good news — up is not always good (wait times). */
  good?: boolean;
}

/** The standard confidence shape (rule 7). Score is 0–100. */
export interface Confidence {
  score: number;
  label?: string;
  rationale?: string;
}

/** Read the many legacy confidence spellings (0.92, 92, "92%", {score}) as 0–100. */
export function toConfidence(value: unknown): Confidence | null {
  if (value == null) return null;
  if (typeof value === 'object' && value !== null && 'score' in value) {
    const c = value as { score: unknown; label?: string; rationale?: string };
    const n = toConfidence(c.score);
    return n ? { ...n, label: c.label, rationale: c.rationale } : null;
  }
  const n = typeof value === 'string' ? parseFloat(value) : typeof value === 'number' ? value : NaN;
  if (!Number.isFinite(n)) return null;
  return { score: Math.round(n <= 1 ? n * 100 : n) };
}

/**
 * The KPI kit's four-value scale (good · warn · bad · neutral), which predates
 * the standard. `info` has no kit colour and reads as neutral there.
 */
export type KitStatus = 'good' | 'warn' | 'bad' | 'neutral';
export function toKitStatus(value: unknown): KitStatus {
  return ({ good: 'good', warning: 'warn', critical: 'bad', info: 'neutral', neutral: 'neutral' } as const)[toStatus(value)];
}
