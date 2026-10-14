import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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

const radiantSubheads = {
  'Proactive Intelligence': 'AI-Ops + E2E Observability',
  'Converged Conversation': 'ConverseAI + Knowledge Hub',
  'Friction Observability': 'Intelligent CX + Agentic Data Platform',
  'Predictive Intelligence': 'Predictive AI + Knowledge Graph',
  'Anomaly Detection': 'Predictive AI + Agentic Data Platform + Agentic AI',
  'Automated Action': 'Multi-Agent Orchestration + MCP',
};

export default function CapabilityCalloutModal({ isOpen, onClose, capability, callouts = [] }) {
  const [activeCapability, setActiveCapability] = useState(capability);

  useEffect(() => {
    if (capability) setActiveCapability(capability);
  }, [capability]);

  if (!activeCapability) return null;

  const DiagramComponent =
    activeCapability.capabilityName && capabilityNameToDiagram[activeCapability.capabilityName];

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
            className="bg-white rounded-2xl relative overflow-hidden flex w-full"
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
                background: '#F7F8FA',
                borderRight: '1px solid #EBEBEB',
                padding: '24px 0',
              }}
            >
              <p
                className="font-semibold px-5 mb-4"
                style={{
                  color: '#999',
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
                        background: isActive ? '#E8EEF7' : 'transparent',
                        color: isActive ? '#003087' : '#555555',
                        boxShadow: 'none',
                        fontWeight: isActive ? 600 : 500,
                      }}
                    >
                      <span
                        className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold"
                        style={{
                          background: isActive ? '#003087' : '#E8E8E8',
                          color: isActive ? '#FFFFFF' : '#888888',
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

              {/* Powered by — bottom of sidebar */}
              <div className="mt-auto px-5 pt-6">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-gray-400 font-medium">Powered by</span>
                  <img
                    src="/radiant-logo.svg"
                    alt="Radiant Digital"
                    className="h-3.5 opacity-60"
                  />
                </div>
              </div>
            </div>

            {/* Right — Title + Architecture diagram */}
            <div className="flex-1 flex flex-col overflow-hidden" style={{ background: '#FAFAFA' }}>
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
                    style={{ backgroundColor: '#003087' }}
                  >
                    Continue
                  </button>

                  {/* Capability content — HTML diagram or SVG fallback */}
                  <div
                    className="flex-1 min-h-0"
                    style={{ overflow: 'hidden' }}
                  >
                    {DiagramComponent ? (
                      <DiagramComponent capability={activeCapability} />
                    ) : null}
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
