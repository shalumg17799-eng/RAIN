import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import ChatThread from './ChatThread';
import ChatInput from './ChatInput';
import SuggestedChips from './SuggestedChips';
import useChatFlow from '@/hooks/useChatFlow';

// `personaId` selects whose script answers. Screens pass it for personas that
// have their own flows; left out, the drawer keeps the generic `ops` script.
export default function ChatDrawer({ isOpen, onClose, preloadedChips = [], initialQuery, personaId }) {
  const {
    ready,
    messages,
    isTyping,
    currentChips,
    handleChipClick,
  } = useChatFlow(personaId);

  const lastQuery = useRef(null);

  // Auto-trigger the initial query when drawer opens with one. Closing clears
  // the guard so asking the same question again after closing still answers.
  useEffect(() => {
    if (!isOpen) {
      lastQuery.current = null;
      return;
    }
    // Wait for the script: a question asked before it loads would go unanswered.
    if (ready && initialQuery && initialQuery !== lastQuery.current) {
      lastQuery.current = initialQuery;
      handleChipClick(initialQuery);
    }
    // lastQuery guards against a re-send when handleChipClick's identity changes.
  }, [isOpen, initialQuery, handleChipClick, ready]);

  const chipsToShow = messages.length === 0 ? preloadedChips : currentChips;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ y: '100%' }}
          animate={{ y: 0 }}
          exit={{ y: '100%' }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="fixed bottom-0 left-[260px] right-0 h-[420px] bg-surface border-t border-border shadow-2xl z-40 flex flex-col rounded-t-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-border-subtle">
            <h3 className="text-sm font-semibold text-brand">Ask the AI</h3>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-surface-2 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4 text-text-subtle" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4">
            <ChatThread
              messages={messages}
              isTyping={isTyping}
              chips={[]}
              onChipClick={handleChipClick}
            />
          </div>

          {/* Chips + Input */}
          <div className="px-4 pb-4 pt-2 border-t border-border-subtle">
            {!isTyping && chipsToShow.length > 0 && (
              <div className="mb-2">
                <SuggestedChips chips={chipsToShow} onChipClick={handleChipClick} />
              </div>
            )}
            <ChatInput onSend={handleChipClick} disabled={isTyping} suggestions={chipsToShow} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
