import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import ChatThread from './ChatThread';
import ChatInput from './ChatInput';
import SuggestedChips from './SuggestedChips';
import useChatFlow from '../../hooks/useChatFlow';
import { usePersona } from '../../context/PersonaContext';

export default function ChatDrawer({ isOpen, onClose, preloadedChips = [], initialQuery }) {
  const persona = usePersona();
  const {
    messages,
    isTyping,
    agentStages,
    hitlRequest,
    respondHitl,
    currentChips,
    handleChipClick,
  } = useChatFlow(persona.id);

  const lastQuery = useRef(null);

  // Auto-trigger the initial query when drawer opens with one
  useEffect(() => {
    if (isOpen && initialQuery && initialQuery !== lastQuery.current) {
      lastQuery.current = initialQuery;
      handleChipClick(initialQuery);
    }
  }, [isOpen, initialQuery]);

  const chipsToShow = messages.length === 0 ? preloadedChips : currentChips;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ y: '100%' }}
          animate={{ y: 0 }}
          exit={{ y: '100%' }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="fixed bottom-0 left-0 lg:left-[260px] right-0 h-[420px] bg-white border-t border-gray-200 shadow-2xl z-40 flex flex-col rounded-t-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-[#003087]">Ask the AI</h3>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4">
            <ChatThread
              messages={messages}
              isTyping={isTyping}
              agentStages={agentStages}
              hitlRequest={hitlRequest}
              onHitlDecide={respondHitl}
              chips={[]}
              onChipClick={handleChipClick}
            />
          </div>

          {/* Chips + Input */}
          <div className="px-4 pb-4 pt-2 border-t border-gray-50">
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
