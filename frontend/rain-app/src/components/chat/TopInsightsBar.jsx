import { AnimatePresence, motion } from 'framer-motion';
import { Zap } from 'lucide-react';
import InsightMiniCard from '../cards/InsightMiniCard';
import { devWarn } from '@core/log';

/**
 * `limit` defaults to the three cards every tenant shows; a persona whose spec
 * names four priority signals (SCLAC) passes 4. Nothing else changes.
 */
export default function TopInsightsBar({ signals, onInsightClick, visible, signalToChip, limit = 3 }) {
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
            <div className="w-5 h-5 rounded-md bg-brand/8 flex items-center justify-center">
              <Zap className="w-3 h-3 text-brand" />
            </div>
            <span className="text-[11px] font-bold text-text-muted uppercase tracking-wider">
              Priority Signals
            </span>
            <div className="flex-1 h-px bg-surface-2 ml-1" />
          </div>

          <div className="flex gap-3">
            {signals.slice(0, limit).map((signal, idx) => (
              <InsightMiniCard
                key={signal.id}
                signal={signal}
                index={idx}
                onClick={() => {
                  const chipText = signalToChip?.[signal.id];
                  if (!chipText) {
                    devWarn(`[ConversationGuard] No chip mapped for signal "${signal.id}" — click blocked.`);
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
