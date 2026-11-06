/**
 * The right-hand context panel, desktop only (secondary visuals). On mobile the
 * chat is full-width; per-turn charts that matter also render inline. Split
 * out of PersonaWorkspace.jsx to keep it under 400 lines.
 */
import { AnimatePresence, motion } from 'framer-motion';

export default function ContextPanelAside({ content }) {
  return (
    <AnimatePresence>
      {content !== null && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="hidden lg:block w-[40%] flex-shrink-0 overflow-y-auto scrollbar-sleek p-5 bg-gradient-to-b from-surface-2 to-bg"
        >
          <AnimatePresence mode="wait">{content}</AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
