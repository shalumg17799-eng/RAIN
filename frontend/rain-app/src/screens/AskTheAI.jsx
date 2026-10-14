import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Sparkles, ArrowRight, ArrowLeft } from 'lucide-react';
import { usePersona } from '../context/PersonaContext';
import ChatThread from '../components/chat/ChatThread';
import ChatInput from '../components/chat/ChatInput';
import useChatFlow from '../hooks/useChatFlow';
import TopInsightsBar from '../components/chat/TopInsightsBar';
import DataOverviewBar from '../components/cards/DataOverviewBar';
import CapabilityCalloutModal from '../components/modals/CapabilityCalloutModal';
// Phone frame is commented out so James uses the same desktop column as the
// other personas. The frame is still the spec's field-app demo (390px column,
// status bar, "RAIN Operations" header, offline-cached badge). Restore it by
// uncommenting this import, OPS_MOBILE_PERSONAS, isOpsMobile, and the return below.
// import MobileAppFrame from '../components/layout/MobileAppFrame';

// Personas presented inside a phone frame as a dedicated mobile app. James Tomley's
// rural operations app (offline-tolerant field views) per the RAIN spec.
// const OPS_MOBILE_PERSONAS = new Set(['rain_tomley']);
import personaUIConfigs from '../data/personaUIConfig';

// RAIN inline component registry — co-located under
// src/clients/rain/askComponents.jsx, assembled in clients/askComponents.
// RAIN personas compose all visuals inline in the chat thread (no right panel).
import { inlineComponentRegistries } from '@/clients/askComponents';
import { KPI_ICON_MAP } from '@/clients/rain/components/RAINComplianceView';

// Backend base URL -- set VITE_API_BASE in .env for a deployed backend;
// defaults to the local dev server.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

// Ultra's persona ids -> the backend's shorter persona ids.
const PERSONA_ID_MAP = {
  rain_delgado: 'maria',
  rain_whitehorse: 'sarah',
  rain_tomley: 'james',
  rain_nair: 'priya',
  rain_yazzie: 'david',
};


function getTimeGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

// ─── Signal data loader ──────────────────────────────────────────
function usePersonaSignals(personaId) {
  const [signals, setSignals] = useState([]);
  const loaded = useRef(null);

  useEffect(() => {
    if (loaded.current === personaId) return;
    loaded.current = personaId;
    const backendId = PERSONA_ID_MAP[personaId];
    if (!backendId) {
      setSignals([]);
      return;
    }
    fetch(`${API_BASE}/ultra/rain/${backendId}/signals`)
      .then((r) => r.json())
      .then(setSignals)
      .catch(() => setSignals([]));
  }, [personaId]);

  return signals;
}

// KPI tiles. Same fetch as the signal cards above. The endpoint fills each
// tile from its database query. The saved numbers in personaUI.js are not
// shown.
function usePersonaKpis(personaId) {
  const [kpis, setKpis] = useState([]);
  const loaded = useRef(null);

  useEffect(() => {
    if (loaded.current === personaId) return;
    loaded.current = personaId;
    const backendId = PERSONA_ID_MAP[personaId];
    if (!backendId) {
      setKpis([]);
      return;
    }
    fetch(`${API_BASE}/ultra/rain/${backendId}/kpis`)
      .then((r) => r.json())
      .then((rows) => {
        if (!Array.isArray(rows)) {
          setKpis([]);
          return;
        }
        setKpis(rows.map((stat) => ({
          ...stat,
          icon: KPI_ICON_MAP[stat.icon] || stat.icon,
        })));
      })
      .catch(() => setKpis([]));
  }, [personaId]);

  return kpis;
}

// ─── Capability callouts loader ──────────────────────────────────
function usePersonaCapabilityCallouts(personaId) {
  const [callouts, setCallouts] = useState([]);
  const loaded = useRef(null);

  useEffect(() => {
    if (loaded.current === personaId) return;
    loaded.current = personaId;
    const calloutImports = {
      rain_delgado: () => import('@/clients/rain/data/delgado/capabilityCallouts.json'),
      rain_whitehorse: () => import('@/clients/rain/data/whitehorse/capabilityCallouts.json'),
      rain_tomley: () => import('@/clients/rain/data/tomley/capabilityCallouts.json'),
      rain_nair: () => import('@/clients/rain/data/nair/capabilityCallouts.json'),
      rain_yazzie: () => import('@/clients/rain/data/yazzie/capabilityCallouts.json'),
    };
    const loader = calloutImports[personaId];
    if (loader) {
      loader().then((mod) => setCallouts(mod.default || mod));
    } else {
      setCallouts([]);
    }
  }, [personaId]);

  return callouts;
}

export default function AskTheAI() {
  const persona = usePersona();
  const personaId = persona.id;
  const uiConfig = personaUIConfigs[personaId];

  const {
    messages,
    isTyping,
    currentChips,
    currentFlowKey,
    handleChipClick,
    initializeFlow,
  } = useChatFlow(personaId);

  const signals = usePersonaSignals(personaId);
  const kpis = usePersonaKpis(personaId);
  const capabilityCallouts = usePersonaCapabilityCallouts(personaId);

  const [capabilityModal, setCapabilityModal] = useState(null);
  const initialized = useRef(false);
  const initializedPersona = useRef(null);

  // Re-initialize whenever the active persona changes (not just on first mount)
  useEffect(() => {
    if (initializedPersona.current === personaId) return;
    initializedPersona.current = personaId;
    initialized.current = true;
    initializeFlow(uiConfig.greetingFlowKey);
  }, [personaId]); // eslint-disable-line react-hooks/exhaustive-deps

  const getCapabilityForMessage = (msg) => {
    if (msg.role !== 'ai' || !msg.flowKey) return undefined;
    const trigger = uiConfig.flowKeyToCapabilityTrigger[msg.flowKey];
    if (!trigger) return undefined;
    return capabilityCallouts.find((c) => c.trigger === trigger) || undefined;
  };

  const handleCapabilityClick = (capability) => {
    setCapabilityModal(capability);
  };

  const renderInlineComponents = (msg) => {
    if (msg.role !== 'ai' || !msg.flowKey) return undefined;

    const components = [];

    const registry = inlineComponentRegistries[personaId];
    if (registry) {
      const fromRegistry = registry(msg, signals);
      if (fromRegistry?.length) components.push(...fromRegistry);
    }

    return components.length > 0 ? components : undefined;
  };

  const chipsToShow = messages.length === 0 ? uiConfig.initialChips : currentChips;
  const recommendedChip = currentFlowKey ? uiConfig.goldenPathChip[currentFlowKey] || null : uiConfig.goldenPathChip[uiConfig.greetingFlowKey];
  const isInitialView = messages.length <= 1 && !isTyping;

  const handleBackToBriefing = () => {
    initialized.current = false;
    initializeFlow(uiConfig.greetingFlowKey);
    initialized.current = true;
    // Snap scroll to top so the greeting + briefing panel are visible without
    // having to scroll up past the chat history.
    if (scrollAreaRef.current) scrollAreaRef.current.scrollTop = 0;
  };

  // Scroll-area ref so we can reliably reset to top when the user lands on
  // (or returns to) the briefing view. Without this, ChatThread's auto-scroll
  // to the latest message can push the viewport down past the greeting.
  const scrollAreaRef = useRef(null);
  useEffect(() => {
    if (isInitialView && scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = 0;
    }
  }, [personaId, isInitialView]);

  // const isOpsMobile = OPS_MOBILE_PERSONAS.has(personaId);
  const mainView = (
    <div className="flex-1 flex h-full">
      {/* Chat area */}
      <motion.div
        className="flex flex-col overflow-hidden h-full min-h-0"
        animate={{ width: '100%' }}
        transition={{ duration: 0.4, ease: 'easeInOut' }}
      >
        {/* Back to Briefing — pinned above scroll area. */}
        <AnimatePresence>
          {!isInitialView && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
              className="flex-shrink-0 bg-white border-b border-gray-100"
            >
              <div className="max-w-3xl mx-auto px-6 py-2">
                <button
                  onClick={handleBackToBriefing}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium text-gray-500 hover:text-[#003087] hover:bg-[#003087]/[0.05] border border-transparent hover:border-[#003087]/10 transition-all duration-200 cursor-pointer -ml-1"
                >
                  <ArrowLeft className="w-3 h-3" />
                  Back to Briefing
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Scrollable content area.
            RAIN's briefing (priority signals + KPI grid) is taller than the
            viewport — `justify-center` would clip the top of the dashboard into
            unreachable overflow, so the welcome view top-aligns and scrolls. */}
        <div
          ref={scrollAreaRef}
          className={`flex-1 overflow-y-auto scrollbar-sleek ${
            isInitialView
              ? 'flex flex-col justify-start pt-2'
              : ''
          }`}
          style={{
            background: isInitialView
              ? 'linear-gradient(180deg, rgba(0,48,135,0.02) 0%, rgba(0,48,135,0.005) 40%, #ffffff 100%)'
              : '#ffffff',
          }}
        >
          <div className="max-w-3xl mx-auto px-6">

            {/* Welcome Hero */}
            <AnimatePresence>
              {isInitialView && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0, overflow: 'hidden' }}
                  transition={{ duration: 0.4 }}
                  className="pt-4 pb-4"
                >
                  <h2 className="text-xl font-bold text-gray-900 tracking-tight">
                    {getTimeGreeting()}, <span className="text-[#003087]">{persona.greeting}</span>
                  </h2>
                  <p className="text-[13px] text-gray-500 mt-1 leading-relaxed">
                    Your AI intelligence brief is ready. Here's what needs your attention today.
                  </p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Signal cards + Data overview */}
            <TopInsightsBar
              signals={signals}
              onInsightClick={handleChipClick}
              visible={isInitialView}
              signalToChip={uiConfig.signalToChip}
            />
            <DataOverviewBar
              key={personaId}
              visible={isInitialView}
              onStatClick={handleChipClick}
              stats={kpis}
            />

            {/* Divider */}
            <AnimatePresence>
              {isInitialView && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="flex items-center gap-3 mb-2"
                >
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent" />
                  <div className="flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-gray-50 border border-gray-100">
                    <Sparkles className="w-3 h-3 text-[#003087]/50" />
                    <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">AI Conversation</span>
                  </div>
                  <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-200 to-transparent" />
                </motion.div>
              )}
            </AnimatePresence>

            <ChatThread
              messages={messages}
              isTyping={isTyping}
              chips={[]}
              onChipClick={handleChipClick}
              renderInlineComponents={renderInlineComponents}
              getCapability={getCapabilityForMessage}
              onCapabilityClick={handleCapabilityClick}
            />
          </div>
        </div>

        {/* Chips + Input area */}
        <div className="relative bg-white">
          <div className="absolute -top-6 left-0 right-0 h-6 bg-gradient-to-t from-white to-transparent pointer-events-none z-10" />

          <div className="max-w-3xl mx-auto px-6 pb-4 pt-2">
            {!isTyping && chipsToShow.length > 0 && (
              <div className="mb-2.5">
                <div className="flex flex-wrap gap-1.5">
                  {chipsToShow.map((chip, idx) => {
                    const isRecommended = chip === recommendedChip;
                    return (
                      <button
                        key={idx}
                        onClick={() => handleChipClick(chip)}
                        className={`group relative px-3.5 py-1.5 rounded-full text-[11px] font-medium border transition-all duration-200 cursor-pointer ${
                          isRecommended
                            ? 'bg-[#003087] text-white border-[#003087] hover:bg-[#002570] shadow-[0_2px_8px_rgba(0,48,135,0.3)]'
                            : 'border-gray-200 text-gray-600 bg-white hover:bg-gray-50 hover:border-[#003087]/30 hover:text-[#003087] shadow-sm hover:shadow'
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          {isRecommended && <ArrowRight className="w-3 h-3" />}
                          {chip}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            <ChatInput
              onSend={handleChipClick}
              disabled={isTyping}
              suggestions={chipsToShow}
              placeholder="Ask anything about your members, signals, or operations…"
            />
          </div>
        </div>
      </motion.div>

      {/* Capability Modal */}
      <CapabilityCalloutModal
        isOpen={!!capabilityModal}
        onClose={() => setCapabilityModal(null)}
        capability={capabilityModal}
        callouts={capabilityCallouts}
      />
    </div>
  );

  // James Tomley's rural operations app was presented inside a phone frame with an
  // offline-cache indicator. Commented out so this screen matches the other
  // personas on a desktop window. Uncomment to put rain_tomley back in the frame.
  // return isOpsMobile ? (
  //   <MobileAppFrame appLabel="RAIN Operations">{mainView}</MobileAppFrame>
  // ) : (
  //   mainView
  // );
  return mainView;
}
