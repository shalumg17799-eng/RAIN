import { AnimatePresence, motion } from 'framer-motion';
import { Zap } from 'lucide-react';
import InsightMiniCard from '../cards/InsightMiniCard';

export default function TopInsightsBar({ signals, onInsightClick, visible, signalToChip }) {
  if (!signals || signals.length === 0) return null;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, height: 'auto' }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0, marginBottom: 0, overflow: 'hidden' }}
          transition={{ duration: 0.3, ease: 'easeInOut' }}
          className="mb-3"
        >
          {/* Section label */}
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded-md bg-[#003087]/8 flex items-center justify-center">
              <Zap className="w-3 h-3 text-[#003087]" />
            </div>
            <span className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">
              Priority Signals
            </span>
            <div className="flex-1 h-px bg-gray-100 ml-1" />
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            {signals.slice(0, 3).map((signal, idx) => (
              <InsightMiniCard
                key={signal.id}
                signal={signal}
                index={idx}
                onClick={() => {
                  // Match by position (1st/2nd/3rd signal), not by exact id
                  // string -- the live backend's signal ids use a different
                  // naming convention (SIG-RAIN-SARAH-001) than Ultra's own
                  // static signalToChip map (SIG-RAIN-WHITEHORSE-001), so an
                  // id-string lookup always misses and silently blocks every
                  // signal-card click. Position is verified to match the
                  // same signal on both sides.
                  const chipKeys = Object.keys(signalToChip || {});
                  const chipText = signalToChip?.[chipKeys[idx]];
                  if (!chipText) {
                    console.warn(`[ConversationGuard] No chip mapped for signal position ${idx} — click blocked.`);
                    return;
                  }
                  if (onInsightClick) onInsightClick(chipText);
                }}
              />
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
