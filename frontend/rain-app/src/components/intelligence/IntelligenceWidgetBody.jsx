import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Zap, Clock } from 'lucide-react';
import InsightMiniCard from '../cards/InsightMiniCard';
import KpiChipStrip from '../briefing/KpiChipStrip';
import { devWarn } from '@core/log';

// Compact section header — same visual language as BriefingPanel so the
// widget reads as a continuation of that surface, not a separate UI.
function SectionHeading({ Icon, iconTint, label }) {
  return (
    <div className="flex items-center gap-2 mb-1.5">
      <div className={`w-5 h-5 rounded-md ${iconTint.bg} flex items-center justify-center`}>
        <Icon className={`w-3 h-3 ${iconTint.fg}`} />
      </div>
      <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
        {label}
      </span>
      <div className="flex-1 h-px bg-surface-2 ml-1" />
    </div>
  );
}

// 360px-wide column. Cards stack vertically (vs. BriefingPanel's 3-across)
// because at this width a 3-up grid crushes the title to a single line and
// drops the metric text. Each card stays in its own row-flex wrapper so the
// internal `flex-1 min-w-0` fills the column without stretching height.
function SignalColumn({ signals, signalToChip, onTileClick }) {
  if (!signals?.length) return null;
  return (
    <div className="space-y-2">
      {signals.map((signal, idx) => (
        <div key={signal.id} className="flex">
          <InsightMiniCard
            signal={signal}
            index={idx}
            onClick={() => {
              const chipText = signalToChip?.[signal.id];
              if (!chipText) {
                devWarn(`[IntelligenceWidget] No chip mapped for signal "${signal.id}"`);
                return;
              }
              onTileClick?.(chipText);
            }}
          />
        </div>
      ))}
    </div>
  );
}

export default function IntelligenceWidgetBody({
  baseline,
  intradayTiers,
  signalToChip = {},
  onTileClick,
}) {
  const liveSignals = useMemo(
    () => (baseline?.priority_signals_inline || []).slice(0, 3),
    [baseline],
  );
  const trendSignals = useMemo(
    () => (baseline?.trend_signals_inline || []).slice(0, 3),
    [baseline],
  );

  if (!baseline) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      {/* KPI strip at the top — operators glance at numbers first */}
      {baseline.tiers && intradayTiers?.length ? (
        <section>
          <KpiChipStrip
            tiers={baseline.tiers}
            availableTiers={intradayTiers}
            onKpiClick={onTileClick}
          />
        </section>
      ) : null}

      {liveSignals.length > 0 ? (
        <section>
          <SectionHeading
            Icon={Zap}
            iconTint={{ bg: 'bg-brand/8', fg: 'text-brand' }}
            label="Intraday / Real-Time"
          />
          <SignalColumn
            signals={liveSignals}
            signalToChip={signalToChip}
            onTileClick={onTileClick}
          />
        </section>
      ) : null}

      {trendSignals.length > 0 ? (
        <section>
          <SectionHeading
            Icon={Clock}
            iconTint={{ bg: 'bg-bg', fg: 'text-text-muted' }}
            label="Trend / Proactive"
          />
          <SignalColumn
            signals={trendSignals}
            signalToChip={signalToChip}
            onTileClick={onTileClick}
          />
        </section>
      ) : null}
    </motion.div>
  );
}
