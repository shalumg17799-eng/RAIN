import { AlertTriangle, TrendingDown, Users, LineChart, ClipboardCheck, CheckCircle2, ArrowRight, type LucideIcon } from 'lucide-react';
import SourceBadge from '../chat/SourceBadge';
import { tierFor, colorFor } from '@/utils/confidence';

// `review` and `healthy` serve governance personas whose signals are assurance
// items rather than incidents (NFCU Platform Admin). Lookup is case-insensitive
// so specs written as REVIEW / HEALTHY / INFO resolve correctly.
interface SeverityStyle { border: string; bg: string; icon: LucideIcon; iconColor: string; dot: string }

/** The signal shape this card draws (the catalog's `signal_card` adapts the standard signal to it). */
export interface SignalCardSignal {
  id?: string;
  title: string;
  description?: string;
  /** critical · warning · info · review · healthy, any case; anything else draws as info. */
  severity?: string;
  affected_count?: number | null;
  sources?: readonly unknown[];
  trend?: string;
  confidence?: { score: number } | null;
  action?: string;
  /** Calm tone only: when it is due. */
  horizon?: string;
}

type Tone = 'urgent' | 'calm';

const severityStyles: Record<string, SeverityStyle> = {
  critical: { border: 'border-critical-200',     bg: 'bg-critical-50',     icon: AlertTriangle,  iconColor: 'text-critical-500',     dot: 'bg-critical-500'     },
  warning:  { border: 'border-warning-200',   bg: 'bg-warning-50',   icon: TrendingDown,   iconColor: 'text-warning-500',   dot: 'bg-warning-500'   },
  info:     { border: 'border-info-200',    bg: 'bg-info-50',    icon: Users,          iconColor: 'text-info-500',    dot: 'bg-info-500'    },
  review:   { border: 'border-indigo-200',  bg: 'bg-indigo-50',  icon: ClipboardCheck, iconColor: 'text-indigo-500',  dot: 'bg-indigo-500'  },
  healthy:  { border: 'border-success-200', bg: 'bg-success-50', icon: CheckCircle2,   iconColor: 'text-success-500', dot: 'bg-success-500' },
};

/** Resolve a signal's severity to a style, case-insensitively, defaulting to info. */
function styleForSeverity(severity: string | undefined): SeverityStyle {
  return severityStyles[String(severity ?? '').toLowerCase()] || severityStyles.info;
}

const calmStyle: SeverityStyle = {
  border: 'border-border',
  bg: 'bg-surface',
  icon: LineChart,
  iconColor: 'text-text-subtle',
  dot: 'bg-text-subtle',
};

// Compact variant — designed for a 3-tile row inside the briefing panel.
// Footprint: small icon + truncated title + 2-line description + tiny meta.
// No source badges, no confidence chip. The chat conversation is where deep
// detail lives.
function CompactCard({ signal, style, tone }: { signal: SignalCardSignal; style: SeverityStyle; tone: Tone }) {
  const Icon = style.icon;
  const isCalm = tone === 'calm';
  const meta = isCalm
    ? signal.horizon
    : signal.affected_count != null
      ? `${signal.affected_count.toLocaleString()} members`
      : null;

  return (
    <div className={`h-full rounded-lg border ${style.border} ${style.bg} p-2 flex flex-col gap-1`}>
      <div className="flex items-center gap-1.5 min-w-0">
        <Icon className={`w-3 h-3 flex-shrink-0 ${style.iconColor}`} />
        <h4 className={`text-[10.5px] font-semibold leading-tight truncate ${isCalm ? 'text-text-muted' : 'text-text'}`}>
          {signal.title}
        </h4>
      </div>
      <p
        className={`text-[10px] leading-snug ${isCalm ? 'text-text-muted' : 'text-text-muted'}`}
        style={{
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {signal.description}
      </p>
      {meta ? (
        <div className="flex items-center justify-between gap-1 mt-auto pt-0.5">
          <span className={`text-[9px] font-medium ${isCalm ? 'text-text-subtle uppercase tracking-wide' : 'text-text-muted'} truncate`}>
            {meta}
          </span>
          {!isCalm && signal.confidence?.score != null ? (
            <span
              className="text-[9px] font-bold tabular-nums flex-shrink-0"
              style={{ color: colorFor(tierFor(signal.confidence.score)) }}
            >
              {signal.confidence.score}%
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/**
 * `showAction` surfaces the signal's recommended action as its own labelled
 * line. Opt-in rather than automatic: several tenants already carry an `action`
 * field that has never been rendered, and switching it on globally would change
 * how their cards look. ESFCU asks for it because its spec types `action` as a
 * first-class part of a signal — a signal without its recommended action is an
 * observation, not a decision.
 */
export interface SignalCardProps {
  signal: SignalCardSignal;
  tone?: Tone;
  compact?: boolean;
  /** Draw the recommended action as its own line. */
  showAction?: boolean;
}

export default function SignalCard({ signal, tone = 'urgent', compact = false, showAction = false }: SignalCardProps) {
  const isCalm = tone === 'calm';
  const style = isCalm ? calmStyle : styleForSeverity(signal.severity);

  if (compact) return <CompactCard signal={signal} style={style} tone={tone} />;

  const Icon = style.icon;
  return (
    <div className={`rounded-xl border ${style.border} ${style.bg} p-4`}>
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 ${style.iconColor}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h4 className={`text-sm font-semibold ${isCalm ? 'text-text-muted' : 'text-text'}`}>
              {signal.title}
            </h4>
            {isCalm && signal.horizon ? (
              <span className="flex-shrink-0 text-[9.5px] font-semibold uppercase tracking-wide text-text-subtle tabular-nums">
                {signal.horizon}
              </span>
            ) : null}
          </div>
          <p className={`text-xs leading-relaxed mb-2 ${isCalm ? 'text-text-muted' : 'text-text-muted'}`}>
            {signal.description}
          </p>
          {!isCalm && (signal.affected_count != null || signal.trend) ? (
            <div className="flex items-center gap-3 text-xs text-text-muted">
              {signal.affected_count != null ? (
                <span className="font-medium">{signal.affected_count.toLocaleString()} members affected</span>
              ) : null}
              {signal.trend ? (
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                  signal.trend === 'worsening' ? 'bg-critical-100 text-critical-800' : 'bg-warning-100 text-warning-800'
                }`}>
                  {signal.trend}
                </span>
              ) : null}
            </div>
          ) : null}
          {showAction && signal.action ? (
            <div className="mt-2 flex items-start gap-1.5 rounded-lg border border-black/[0.06] bg-white/70 px-2.5 py-1.5">
              <ArrowRight className="mt-[3px] h-3 w-3 flex-shrink-0 text-text-subtle" />
              <p className="text-[11px] leading-snug text-text-muted">
                <span className="font-semibold uppercase tracking-wide text-[9.5px] text-text-subtle">Action</span>
                {' · '}
                {signal.action}
              </p>
            </div>
          ) : null}
          {(signal.sources || signal.confidence) && (
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              {signal.sources && signal.sources.map((s, i: number) => <SourceBadge key={i} source={s} />)}
              {signal.confidence && (
                <span
                  className="ml-auto text-[10px] font-semibold tabular-nums"
                  style={{ color: colorFor(tierFor(signal.confidence.score)) }}
                >
                  Confidence {signal.confidence.score}%
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
