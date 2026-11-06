import { useState } from 'react';
import ChatInput from '@/components/chat/ChatInput';
import ChatDrawer from '@/components/chat/ChatDrawer';

/**
 * The frame every non-chat page shares: the page's content, a persistent
 * question bar along the bottom, and the chat drawer it opens. The page
 * supplies its content and its starter questions; the frame owns the drawer.
 *
 * Props: { chips, placeholder, personaId?, children }
 *   personaId — whose script answers in the drawer; omitted, the generic one.
 */
export default function AskablePage({ chips, placeholder, personaId, children }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState(null);
  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-64px)]">
      {children}

      {/* Persistent Chat Input */}
      <div className="fixed bottom-0 left-[260px] right-0 bg-surface border-t border-border px-6 py-4 z-30">
        <div className="max-w-3xl mx-auto">
          <ChatInput
            onSend={(text) => { setInitialQuery(text); setDrawerOpen(true); }}
            placeholder={placeholder}
            suggestions={chips}
          />
        </div>
      </div>

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
