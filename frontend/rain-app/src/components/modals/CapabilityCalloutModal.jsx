// @ultra-shell: the workspace's capability modal. Rule 5 lets the shell read context.
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useBranding } from '@/context/BrandingContext';
import ProactiveIntelligenceDiagram from '../capabilities/ProactiveIntelligenceDiagram';
import TalkToDataDiagram from '../capabilities/TalkToDataDiagram';
import BehavioralSegmentationDiagram from '../capabilities/BehavioralSegmentationDiagram';
import PredictiveIntelligenceDiagram from '../capabilities/PredictiveIntelligenceDiagram';
import ActionExecutionDiagram from '../capabilities/ActionExecutionDiagram';
import AnomalyDetectionDiagram from '../capabilities/AnomalyDetectionDiagram';

// Map by capability name so the correct diagram renders regardless of trigger index
const capabilityNameToDiagram = {
  'Proactive Intelligence': ProactiveIntelligenceDiagram,
  'Converged Conversation': TalkToDataDiagram,
  'Friction Observability': BehavioralSegmentationDiagram,
  'Predictive Intelligence': PredictiveIntelligenceDiagram,
  'Anomaly Detection': AnomalyDetectionDiagram,
  'Automated Action': ActionExecutionDiagram,
};

// Which entry of the persona's `capabilityDiagrams` each diagram reads.
const capabilityNameToKind = {
  'Proactive Intelligence': 'proactive',
  'Converged Conversation': 'converged',
  'Friction Observability': 'friction',
  'Predictive Intelligence': 'predictive',
  'Anomaly Detection': 'anomaly',
  'Automated Action': 'action',
};

export default function CapabilityCalloutModal({ isOpen, onClose, capability, callouts = [], diagrams }) {
  const { client } = useBranding();
  const [activeCapability, setActiveCapability] = useState(capability);
  // Follow the capability that opened the modal; keep the last one while it
  // closes (capability goes null) so the exit animation has content.
  const [openedWith, setOpenedWith] = useState(capability);
  if (capability !== openedWith) {
    setOpenedWith(capability);
    if (capability) setActiveCapability(capability);
  }

  if (!activeCapability) return null;

  // `diagram` lets a tenant show its own label (SCLAC's plain-language names) and keep the platform diagram.
  const diagramName = activeCapability.diagram ?? activeCapability.capabilityName;
  const DiagramComponent = diagramName && capabilityNameToDiagram[diagramName];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.60)', padding: '1vh 1vw' }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 16 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="bg-surface rounded-2xl relative overflow-hidden flex w-full"
            style={{
              boxShadow: '0px 24px 48px rgba(0,0,0,0.20)',
              width: '98vw',
              height: '98vh',
              maxWidth: '98vw',
              maxHeight: '98vh',
            }}
          >
            {/* Left sidebar — capability tabs */}
            <div
              className="flex flex-col flex-shrink-0"
              style={{
                width: '200px',
                background: 'var(--color-surface-2)',
                borderRight: '1px solid var(--color-border)',
                padding: '24px 0',
              }}
            >
              <p
                className="font-semibold px-5 mb-4"
                style={{
                  color: 'var(--color-text-subtle)',
                  fontSize: '10px',
                  textTransform: 'uppercase',
                  letterSpacing: '2px',
                }}
              >
                AI Capabilities
              </p>
              <div className="flex flex-col gap-1 px-3">
                {callouts.map((cap, idx) => {
                  const isActive = cap.trigger === activeCapability.trigger;
                  return (
                    <button
                      key={cap.trigger}
                      onClick={() => setActiveCapability(cap)}
                      className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all cursor-pointer"
                      style={{
                        background: isActive ? 'var(--color-brand-subtle)' : 'transparent',
                        color: isActive ? 'var(--color-brand)' : 'var(--color-text-muted)',
                        boxShadow: 'none',
                        fontWeight: isActive ? 600 : 500,
                      }}
                    >
                      <span
                        className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold"
                        style={{
                          background: isActive ? 'var(--color-brand)' : 'var(--color-border)',
                          color: isActive ? 'var(--color-brand-fg)' : 'var(--color-text-subtle)',
                        }}
                      >
                        {idx + 1}
                      </span>
                      <span className="text-xs font-medium leading-tight">
                        {cap.capabilityName}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Powered by — bottom of sidebar. Radiant by default; a client
                  that supplies `footerMark` leads with its own product brand
                  here too, matching the sidebar footer. */}
              <div className="mt-auto px-5 pt-6">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-text-subtle font-medium">
                    {client?.footerMark?.label ?? 'Powered by'}
                  </span>
                  <img
                    src={client?.footerMark?.logo ?? '/radiant-logo.svg'}
                    alt={client?.footerMark?.alt ?? 'Radiant Digital'}
                    // Client lockups are stacked; Radiant's is horizontal.
                    className={client?.footerMark ? 'h-7 opacity-90' : 'h-3.5 opacity-60'}
                  />
                </div>
              </div>
            </div>

            {/* Right — Title + Architecture diagram */}
            <div className="flex-1 flex flex-col overflow-hidden" style={{ background: 'var(--color-surface-2)' }}>
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeCapability.trigger}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.25, ease: 'easeOut' }}
                  className="relative flex flex-col h-full"
                  style={{ padding: '12px 16px 12px' }}
                >
                  {/* Continue button — fixed top-right over the SVG */}
                  <button
                    onClick={onClose}
                    className="absolute top-14 right-5 z-10 px-5 py-2 rounded-lg text-sm font-semibold text-white transition-colors cursor-pointer hover:opacity-90"
                    style={{ backgroundColor: 'var(--color-brand)' }}
                  >
                    Continue
                  </button>

                  {/* Capability content — HTML diagram or SVG fallback */}
                  <div
                    className="flex-1 min-h-0"
                    style={{ overflow: 'hidden' }}
                  >
                    {DiagramComponent ? (
                      <DiagramComponent content={diagrams?.[capabilityNameToKind[diagramName]]} clientName={client?.shortName} />
                    ) : (
                      // Capabilities without a bespoke architecture diagram (e.g. the
                      // governance capabilities) fall back to a readable description.
                      <div className="h-full flex items-center justify-center p-8">
                        <div className="max-w-xl text-center">
                          {activeCapability.eyebrow && (
                            <p className="text-[11px] font-bold uppercase tracking-[2px] text-brand/70 mb-3">
                              {activeCapability.eyebrow}
                            </p>
                          )}
                          <h2 className="text-2xl font-bold text-text mb-4">{activeCapability.capabilityName}</h2>
                          <p className="text-sm text-text-muted leading-relaxed">{activeCapability.description}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
