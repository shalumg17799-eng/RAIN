/**
 * A "signal" — a proactively-surfaced insight the AI raises to the persona
 * (queue spike, fraud pattern, churn surge…). Shapes vary across demos, so the
 * runtime-critical fields are typed and the rest is left open.
 */

export interface ConfidenceScore {
  score: number;
  rationale?: string;
  /** Opt-in: shown after the score ("94% confidence"), with the rationale on hover. */
  label?: string;
  [key: string]: unknown;
}

export interface Signal {
  id: string;
  type?: string;
  title: string;
  description?: string;
  impact?: 'low' | 'medium' | 'high' | string;
  severity?: 'info' | 'warning' | 'critical' | string;
  affected_count?: number;
  sources?: string[];
  timestamp?: string;
  trend?: string;
  /** Some demos flag one hero signal per persona. */
  primary?: boolean;
  metrics?: Record<string, unknown>;
  confidence?: ConfidenceScore;
  /** Demo data carries many persona-specific extras; keep them addressable. */
  [key: string]: unknown;
}
