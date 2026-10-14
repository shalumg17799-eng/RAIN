import { useState } from 'react';
import { RAINPriorityCards, RAINKpiCards } from '@/clients/rain/components/RAINComplianceView';
import ChatInput from '../components/chat/ChatInput';
import ChatDrawer from '../components/chat/ChatDrawer';
import { usePersona } from '../context/PersonaContext';
import { personaUIConfigs } from '@/clients/personaConfigs';

export default function RiskSignals() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState(null);
  const persona = usePersona();

  // Was hardcoded to Dr. Delgado-Reyes's own questions regardless of which
  // persona was viewing -- for every other persona, none of those 5
  // questions exist in their own chatFlows and there's no __default__
  // fallback, so clicking any of them silently produced nothing. Each
  // persona's own real suggested questions already live in personaUI.js.
  const screenChips = personaUIConfigs[persona.id]?.initialChips?.slice(0, 5) || [];
  const inputPlaceholder = 'Ask about maternal, chronic disease, transport, or access signals…';
  const leftColLabel = 'Active Care & Risk Signals';
  const rightColLabel = 'Rural Health KPIs';

  const openDrawerWithQuery = (query) => {
    setInitialQuery(query);
    setDrawerOpen(true);
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-64px)]">
      <div className="flex-1 overflow-y-auto">
        <div className="flex flex-col lg:flex-row gap-6 px-4 lg:px-6 py-6 pb-24">
          {/* Left Column */}
          <div className="w-full lg:w-1/2 space-y-5">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">{leftColLabel}</h2>
            <RAINPriorityCards personaId={persona.id} onSignalClick={openDrawerWithQuery} />
          </div>

          {/* Right Column */}
          <div className="w-1/2 space-y-5">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">{rightColLabel}</h2>
            <RAINKpiCards personaId={persona.id} />
          </div>
        </div>
      </div>

      {/* Persistent Chat Input with pre-loaded chips */}
      <div className="fixed bottom-0 left-0 lg:left-[260px] right-0 bg-white border-t border-gray-200 px-4 lg:px-6 py-4 z-30">
        <div className="max-w-4xl mx-auto">
          <div className="flex flex-wrap gap-2 mb-3">
            {screenChips.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => openDrawerWithQuery(chip)}
                className="px-3 py-1.5 rounded-full text-xs font-medium border border-[#003087]/20 text-[#003087] bg-white hover:bg-[#003087]/5 transition-all cursor-pointer"
              >
                {chip}
              </button>
            ))}
          </div>
          <ChatInput
            onSend={(text) => openDrawerWithQuery(text)}
            placeholder={inputPlaceholder}
            suggestions={screenChips}
          />
        </div>
      </div>

      {/* Chat Drawer */}
      <ChatDrawer
        isOpen={drawerOpen}
        onClose={() => { setDrawerOpen(false); setInitialQuery(null); }}
        preloadedChips={screenChips}
        initialQuery={initialQuery}
      />
    </div>
  );
}
