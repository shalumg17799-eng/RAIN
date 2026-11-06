import { motion } from 'framer-motion';
import JourneyPhase from './JourneyPhase';

export default function JourneyRail({ phases, activePhaseId, onPhaseClick }) {
  return (
    <div className="w-full">
      <div className="flex items-center gap-3 overflow-x-auto pb-2 px-1 scrollbar-thin">
        {phases.map((phase, idx) => (
          <motion.div
            key={phase.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: idx * 0.08 }}
            className="flex items-center"
          >
            <JourneyPhase
              phase={phase}
              isActive={activePhaseId === phase.id}
              onClick={onPhaseClick}
            />
            {idx < phases.length - 1 && (
              <div className="w-6 h-0.5 bg-border flex-shrink-0 mx-0.5" />
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
}
