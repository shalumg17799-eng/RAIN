import { useState } from 'react';
import ChatInput from '@/components/chat/ChatInput';
import ChatDrawer from '@/components/chat/ChatDrawer';

/**
 * The signals page frame: two labelled columns of cards, starter questions as
 * chips above the question bar, and the chat drawer they open. The generic
 * Risk Signals page, and the shape tenants reuse with their own cards.
 *
 * Props: { leftLabel, rightLabel, left, right, chips, placeholder, personaId? }
 */
export default function SignalsColumnsPage({ leftLabel, rightLabel, left, right, chips, placeholder, personaId }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState(null);
  const ask = (query) => { setInitialQuery(query); setDrawerOpen(true); };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-64px)]">
      <div className="flex-1 overflow-y-auto">
        <div className="flex gap-6 px-6 py-6 pb-24">
          {/* Left Column */}
          <div className="w-1/2 space-y-5">
            <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider">{leftLabel}</h2>
            {left}
          </div>

          {/* Right Column */}
          <div className="w-1/2 space-y-5">
            <h2 className="text-sm font-semibold text-text-muted uppercase tracking-wider">{rightLabel}</h2>
            {right}
          </div>
        </div>
      </div>

      {/* Persistent Chat Input with pre-loaded chips */}
      <div className="fixed bottom-0 left-[260px] right-0 bg-surface border-t border-border px-6 py-4 z-30">
        <div className="max-w-4xl mx-auto">
          <div className="flex flex-wrap gap-2 mb-3">
            {chips.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => ask(chip)}
                className="px-3 py-1.5 rounded-full text-xs font-medium border border-brand/20 text-brand bg-surface hover:bg-brand/5 transition-all cursor-pointer"
              >
                {chip}
              </button>
            ))}
          </div>
          <ChatInput onSend={ask} placeholder={placeholder} suggestions={chips} />
        </div>
      </div>

      {/* Chat Drawer */}
      <ChatDrawer
        isOpen={drawerOpen}
        onClose={() => { setDrawerOpen(false); setInitialQuery(null); }}
        preloadedChips={chips}
        initialQuery={initialQuery}
        personaId={personaId}
      />
    </div>
  );
}
