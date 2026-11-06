import { motion } from 'framer-motion';
import { AlertTriangle, TrendingDown, Activity, ChevronRight, LineChart, ClipboardCheck, CheckCircle2 } from 'lucide-react';
import { tierFor, colorFor } from '@/utils/confidence';
import type { ComponentType } from 'react';

/** A signal as the briefing row draws it (legacy keys; see contract/signal for the standard shape). */
export interface InsightSignal {
  id: string;
  title: string;
  severity?: string;
  trend?: string;
  badgeLabel?: string;
  metric_text?: string;
  metrics?: Record<string, string | number | undefined>;
  affected_count?: number;
  type?: string;
  confidence?: { score: number; label?: string; rationale?: string };
}

interface SeverityStyle {
  accent: string;
  iconBg: string;
  icon: ComponentType<{ className?: string }>;
  iconColor: string;
  badge: string;
  badgeLabel: string;
}

const severityConfig: Record<string, SeverityStyle> = {
  critical: {
    accent: 'bg-critical-500',
    iconBg: 'bg-critical-50',
    icon: AlertTriangle,
    iconColor: 'text-critical-500',
    badge: 'text-critical-800 bg-critical-50',
    badgeLabel: 'Critical',
  },
  warning: {
    accent: 'bg-warning-500',
    iconBg: 'bg-warning-50',
    icon: TrendingDown,
    iconColor: 'text-warning-500',
    badge: 'text-warning-800 bg-warning-50',
    badgeLabel: 'Warning',
  },
  info: {
    accent: 'bg-info-500',
    iconBg: 'bg-info-50',
    icon: Activity,
    iconColor: 'text-info-500',
    badge: 'text-info-800 bg-info-50',
    badgeLabel: 'Info',
  },
  // Calm tone for trend / proactive insights. Slate accent + LineChart icon —
  // visually paired with the urgent row but reads as "review when ready".
  watch: {
    accent: 'bg-text-subtle',
    iconBg: 'bg-surface-2',
    icon: LineChart,
    iconColor: 'text-text-muted',
    badge: 'text-text-muted bg-surface-2',
    badgeLabel: 'Watch',
  },
  // Governance personas (NFCU Platform Admin) surface assurance items, not
  // incidents: something to confirm, or something already healthy.
  review: {
    accent: 'bg-indigo-500',
    iconBg: 'bg-indigo-50',
    icon: ClipboardCheck,
    iconColor: 'text-indigo-500',
    badge: 'text-indigo-700 bg-indigo-50',
    badgeLabel: 'Review',
  },
  healthy: {
    accent: 'bg-success-500',
    iconBg: 'bg-success-50',
    icon: CheckCircle2,
    iconColor: 'text-success-500',
    badge: 'text-success-800 bg-success-50',
    badgeLabel: 'Healthy',
  },
};

function formatMetric(signal: InsightSignal): string {
  // Explicit override — preferred for new (intraday/trend) signals so the
  // metric line stays one short, hand-tuned sentence.
  if (signal.metric_text) return signal.metric_text;

  const m = signal.metrics || {};

  // Legacy ops signals
  if (signal.id === 'SIG-001') return `${(signal.affected_count ?? 0).toLocaleString()} members affected`;
  if (signal.id === 'SIG-002') return `${m.abandonment_increase_factor}x increase in abandonment`;
  if (signal.id === 'SIG-003') return `NPS dropped ${m.nps_decline_points} points`;

  // NFCU — type-aware metric lines
  switch (signal.type) {
    case 'queue_spike':
      return m.members_waiting
        ? `${m.members_waiting} waiting · ${m.avg_wait_time} avg wait`
        : `${signal.affected_count} waiting`;
    case 'staffing_risk':
      return m.predicted_service_level
        ? `SL at risk: ${m.predicted_service_level} without action`
        : `${signal.affected_count} agents short`;
    case 'sentiment_decline':
      return m.negative_sentiment_increase
        ? `${m.negative_sentiment_increase} increase in negative sentiment`
        : 'Sentiment decline detected';
    case 'volume_surge':
      return m.agents_needed_peak && m.agents_scheduled_peak
        ? `${Number(m.agents_needed_peak) - Number(m.agents_scheduled_peak)}-agent gap · ${m.volume_increase_predicted} increase`
        : 'Volume surge predicted';
    case 'training_gap':
      return m.current_aht
        ? `AHT ${m.current_aht} vs ${m.target_aht} target · ${m.kb_adherence} KB adherence`
        : `${signal.affected_count} agents behind`;
    case 'budget_risk':
      return m.budget_used_pct
        ? `${m.budget_used_pct} of Q2 budget · ${m.weeks_remaining} wks left`
        : 'Budget at risk';
    case 'compliance_gap':
      return m.accounts_at_risk
        ? `${m.accounts_at_risk} accounts at risk · ${m.skip_rate_this_week} skip rate`
        : 'Compliance gap detected';
    case 'repeat_contact':
      return m.fcr_bill_pay_before
        ? `FCR dropped ${m.fcr_bill_pay_before} → ${m.fcr_bill_pay_now}`
        : 'Repeat contacts elevated';
    case 'agent_burnout':
      return `${signal.affected_count} top agents showing burnout signals`;
    default:
      return (signal.affected_count ?? 0) > 0
        ? `${(signal.affected_count ?? 0).toLocaleString()} affected`
        : 'Action required';
  }
}

export interface InsightMiniCardProps {
  signal: InsightSignal;
  onClick?: () => void;
  /** Position in the row, for the staggered entrance. */
  index?: number;
}

export default function InsightMiniCard({ signal, onClick, index = 0 }: InsightMiniCardProps) {
  // Trend signals don't carry a severity — they carry `trend: "watch"`.
  // Fall through to severity first, then trend, then info.
  // Case-insensitive so specs written as REVIEW / HEALTHY / INFO resolve too.
  const variantKey = String(signal.severity || signal.trend || 'info').toLowerCase();
  const config = severityConfig[variantKey] || severityConfig.info;
  const Icon = config.icon;

  return (
    <motion.button
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.08, ease: 'easeOut' }}
      onClick={onClick}
      className="flex-1 min-w-0 relative overflow-hidden rounded-xl bg-surface border border-border-subtle/80 text-left cursor-pointer group hover:shadow-[0_4px_16px_color-mix(in_srgb,var(--color-brand)_7%,transparent)] hover:border-brand/15 transition-all duration-200"
      style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}
    >
      {/* Top accent line */}
      <div className={`absolute top-0 left-0 right-0 h-[2px] ${config.accent}`} />

      <div className="px-3.5 py-2.5">
        {/* Header row */}
        <div className="flex items-center justify-between mb-1.5">
          <div className={`w-6 h-6 rounded-md flex items-center justify-center ${config.iconBg}`}>
            <Icon className={`w-3 h-3 ${config.iconColor}`} />
          </div>
          <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full ${config.badge}`}>
            {signal.badgeLabel || config.badgeLabel}
          </span>
        </div>

        {/* Title */}
        <p className="text-[12px] font-semibold text-text leading-snug line-clamp-2 mb-1 group-hover:text-brand transition-colors">
          {signal.title}
        </p>

        {/* Metric */}
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] text-text-subtle font-medium truncate">
            {formatMetric(signal)}
          </p>
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {signal.confidence && (
              // `confidence.label` is opt-in data (the Comptroller sets "confidence"):
              // it names the number and puts the rationale on hover. Signals
              // without it render exactly as before.
              <span
                className="text-[10px] font-semibold tabular-nums"
                style={{ color: colorFor(tierFor(signal.confidence.score)) }}
                title={signal.confidence.label ? signal.confidence.rationale : undefined}
              >
                {signal.confidence.score}%{signal.confidence.label ? ` ${signal.confidence.label}` : ''}
              </span>
            )}
            <ChevronRight className="w-3 h-3 text-text-subtle group-hover:text-brand group-hover:translate-x-0.5 transition-all" />
          </div>
        </div>
      </div>
    </motion.button>
  );
}
