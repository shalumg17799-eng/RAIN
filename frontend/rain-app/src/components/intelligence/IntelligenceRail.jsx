import { motion } from 'framer-motion';
import { ChevronLeft, Zap } from 'lucide-react';

// Collapsed 44px vertical rail. Click expands the widget back to its 360px
// briefing panel. Pulse dot reads as "live data"; critical-count badge surfaces
// when there's at least one critical priority signal so an operator can spot
// a worsening situation even when the panel is collapsed.
export default function IntelligenceRail({ criticalCount = 0, onExpand }) {
  return (
    <motion.button
      type="button"
      onClick={onExpand}
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 12 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      title="Open Intelligence panel"
      className="absolute top-0 right-0 bottom-0 w-11 bg-surface border-l border-border/80 shadow-[-2px_0_12px_color-mix(in_srgb,var(--color-brand)_4%,transparent)] flex flex-col items-center pt-3 pb-3 cursor-pointer hover:bg-brand/[0.02] hover:border-brand/30 transition-colors group"
    >
      {/* Pulse dot — live indicator */}
      <div className="relative mb-3">
        <motion.span
          className="block w-2 h-2 rounded-full bg-success-500"
          animate={{ opacity: [1, 0.35, 1] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
        />
        {criticalCount > 0 ? (
          <span className="absolute -top-1.5 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-critical-500 text-white text-[9px] font-bold flex items-center justify-center tabular-nums">
            {criticalCount > 9 ? '9+' : criticalCount}
          </span>
        ) : null}
      </div>

      {/* Rotated label fills the rail vertically */}
      <div className="flex-1 flex items-center justify-center">
        <span
          className="text-[10px] font-bold uppercase tracking-[0.18em] text-brand/80 whitespace-nowrap"
          style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
        >
          Intelligence
        </span>
      </div>

      {/* Expand affordance — chevron + small icon */}
      <div className="flex flex-col items-center gap-1 mt-2">
        <ChevronLeft className="w-3 h-3 text-text-subtle group-hover:text-brand transition-colors" />
        <div className="w-5 h-5 rounded-md bg-brand/8 flex items-center justify-center">
          <Zap className="w-3 h-3 text-brand" />
        </div>
      </div>
    </motion.button>
  );
}
