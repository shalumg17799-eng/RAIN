import { useState } from 'react';
import ChatInput from '../components/chat/ChatInput';
import ChatDrawer from '../components/chat/ChatDrawer';
import { RAINPriorityCards, RAINKpiCards } from '@/clients/rain/components/RAINComplianceView';
import { usePersona } from '../context/PersonaContext';
import { personaUIConfigs } from '@/clients/personaConfigs';

export default function MemberJourney() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState(null);
  const persona = usePersona();

  // Was hardcoded to Dr. Delgado-Reyes's own questions regardless of which
  // persona was viewing -- same bug as RiskSignals.jsx. Each persona's own
  // real suggested questions already live in personaUI.js.
  const rainIntelChips = personaUIConfigs[persona.id]?.initialChips?.slice(0, 4) || [];
  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-64px)]">
      <div className="flex-1 overflow-y-auto scrollbar-sleek px-6 pt-6 pb-28">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-1">Rural Health Intelligence</h2>
        <p className="text-[12px] text-gray-500 mb-4 max-w-2xl">
          Cross-system correlations across clinical EHR, telehealth, remote patient monitoring, claims,
          transportation, public health, and SDOH data that no single rural Nevada health system surfaces natively.
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-5xl">
          <div className="space-y-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">Priority Signals</h3>
            <RAINPriorityCards personaId={persona.id} onSignalClick={(text) => { setInitialQuery(text); setDrawerOpen(true); }} />
          </div>
          <div className="space-y-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">Cross-System KPIs</h3>
            <RAINKpiCards personaId={persona.id} />
          </div>
        </div>
      </div>

      <div className="fixed bottom-0 left-0 lg:left-[260px] right-0 bg-white border-t border-gray-200 px-4 lg:px-6 py-4 z-30">
        <div className="max-w-3xl mx-auto">
          <ChatInput
            onSend={(text) => { setInitialQuery(text); setDrawerOpen(true); }}
            placeholder="Ask across clinical, telehealth, RPM, claims, transport, and SDOH data…"
            suggestions={rainIntelChips}
          />
        </div>
      </div>

      <ChatDrawer
        isOpen={drawerOpen}
        onClose={() => { setDrawerOpen(false); setInitialQuery(null); }}
        preloadedChips={rainIntelChips}
        initialQuery={initialQuery}
      />
    </div>
  );
}
