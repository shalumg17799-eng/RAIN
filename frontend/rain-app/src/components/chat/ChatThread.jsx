import { useRef, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import ChatMessage from './ChatMessage';
import TypingIndicator from './TypingIndicator';
import SuggestedChips from './SuggestedChips';

export default function ChatThread({ messages, isTyping, chips, onChipClick, renderInlineComponents, getCapability, onCapabilityClick }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  return (
    <div className="flex-1 overflow-y-auto py-3 scrollbar-sleek">
      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {messages.map((msg, idx) => (
            <ChatMessage
              key={msg.id || idx}
              message={msg}
              inlineComponents={renderInlineComponents ? renderInlineComponents(msg) : undefined}
              capability={getCapability ? getCapability(msg) : undefined}
              onCapabilityClick={onCapabilityClick}
            />
          ))}
        </AnimatePresence>

        <AnimatePresence>
          {isTyping && <TypingIndicator />}
        </AnimatePresence>

        {!isTyping && chips && chips.length > 0 && (
          <SuggestedChips chips={chips} onChipClick={onChipClick} />
        )}
      </div>
      <div ref={bottomRef} />
    </div>
  );
}
