import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import JourneyRail from './JourneyRail';
import FrictionHotspot from './FrictionHotspot';
import AskablePage from '@/components/layout/AskablePage';

const MEMBER_JOURNEY_LABELS = {
  rail: 'Member Journey Map',
  all: 'All Friction Hotspots',
  phase: 'Friction Points — ',
  empty: 'No friction hotspots in this phase',
  placeholder: 'Ask about this journey…',
};

/**
 * A journey map page: phases on a rail, the hotspots of the selected phase (or
 * all of them), and the question bar. The generic Member Journey page, and the
 * shape tenants reuse with their own map and words (NFCU's workforce view).
 *
 * Props: { map: { phases }, chips, labels?, personaId? }
 */
export default function JourneyMapPage({ map, chips, labels = MEMBER_JOURNEY_LABELS, personaId }) {
  const [activePhaseId, setActivePhaseId] = useState(null);
  const activePhase = map.phases.find((p) => p.id === activePhaseId);
  const hotspots = activePhase
    ? activePhase.frictionHotspots
    : map.phases.flatMap((p) => p.frictionHotspots.map((h) => ({ ...h, phaseName: p.name })));

  return (
    <AskablePage chips={chips} placeholder={labels.placeholder} personaId={personaId}>
      {/* Rail */}
      <div className="px-6 pt-6 pb-4">
        <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">{labels.rail}</h2>
        <JourneyRail
          phases={map.phases}
          activePhaseId={activePhaseId}
          onPhaseClick={(phase) => setActivePhaseId(activePhaseId === phase.id ? null : phase.id)}
        />
      </div>

      {/* Hotspots / Issues */}
      <div className="flex-1 overflow-y-auto scrollbar-sleek px-6 pb-24">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text-muted">
            {activePhase ? `${labels.phase}${activePhase.name}` : labels.all}
          </h3>
          {activePhase && (
            <button
              onClick={() => setActivePhaseId(null)}
              className="text-xs text-brand font-medium hover:underline cursor-pointer"
            >
              Show all
            </button>
          )}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={activePhaseId || 'all'}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="space-y-4"
          >
            {hotspots.length > 0 ? (
              hotspots.map((hotspot, idx) => (
                <FrictionHotspot key={idx} hotspot={hotspot} index={idx} />
              ))
            ) : (
              <div className="text-center py-12 text-sm text-text-subtle">
                {labels.empty}
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </AskablePage>
  );
}
