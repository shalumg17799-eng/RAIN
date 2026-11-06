// @ultra-shell: the workspace's chat thread. Rule 5 lets the shell read context.
import { motion } from 'framer-motion';
import { Bot } from 'lucide-react';
import { usePersona } from '@/context/PersonaContext';
import SourceBadge from './SourceBadge';
import VizErrorBoundary from './VizErrorBoundary';
import CapabilityBadge from './CapabilityBadge';
import ConfidenceTierBadge from './confidence/ConfidenceTierBadge';
import EscalationNotice from './confidence/EscalationNotice';
import ReviewBadge from './confidence/ReviewBadge';
import MessageFeedback from './feedback/MessageFeedback';

/**
 * Renders inline `**bold**` inside a line.
 *
 * The scripted flows have always been authored with markdown emphasis — 284
 * spans across five NFCU personas — but nothing ever parsed it, so every one
 * rendered as literal asterisks ("**Sovereignty.** 0 PII to the frontier").
 * This is deliberately just bold: the flows use no other markdown, and a full
 * parser would be a dependency and an injection surface for zero extra benefit.
 */
function renderInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    const m = part.match(/^\*\*([^*]+)\*\*$/);
    if (!m) return part;
    return <strong key={i} className="font-semibold text-text">{m[1]}</strong>;
  });
}

/**
 * Optional, off by default (every existing caller renders as before):
 * `fullWidth` lets an AI answer span the whole column instead of the readable
 * measure, so the text lines up with the cards under it (SCLAC's Ask the KPI);
 * `compact` drops the avatar gutter and tightens the bubble for a narrow side panel.
 */
export default function ChatMessage({ message, inlineComponents, capability, onCapabilityClick, wideInlineComponents = false, fullWidth = false, compact = false }) {
  const persona = usePersona();
  const isUser = message.role === 'user';
  const confidence = !isUser ? message.confidence : null;

  // An AI answer that carries a site plan or a roll-up table needs the whole
  // column; the 85% cap that keeps prose readable is what pushes those artefacts
  // into a horizontal scroll. Widen the wrapper only for messages that actually
  // have components, and hold the text bubble at its readable measure so the
  // prose does not stretch with it.
  const isWide = (wideInlineComponents && !isUser && inlineComponents?.length > 0) || (fullWidth && !isUser);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`flex items-start gap-3 ${isUser ? 'justify-end' : ''}`}
    >
      {/* AI avatar */}
      {!isUser && !compact && (
        <div className="w-8 h-8 rounded-xl bg-brand/[0.12] flex items-center justify-center flex-shrink-0 mt-0.5">
          <Bot className="w-4 h-4 text-brand/70" />
        </div>
      )}

      <div className={`min-w-0 ${isWide ? 'flex-1' : 'max-w-[85%]'} ${isUser ? 'order-first' : ''}`}>
        {/* Message bubble */}
        <div
          className={`rounded-2xl ${compact ? 'px-4 py-3' : 'px-5 py-3.5'} text-sm leading-relaxed ${isWide && !fullWidth ? 'max-w-3xl' : ''} ${
            isUser
              ? 'bg-gradient-to-br from-brand to-[color-mix(in_srgb,var(--color-brand)_85%,#fff)] text-white rounded-tr-md shadow-[0_2px_8px_color-mix(in_srgb,var(--color-brand)_20%,transparent)]'
              : 'bg-surface text-text rounded-tl-md border border-border/70'
          }`}
          style={!isUser ? { boxShadow: '0 1px 6px rgba(0,0,0,0.06)' } : {}}
        >
          {message.text.split('\n').map((line, i) => {
            if (!line.trim()) return <div key={i} className="h-2.5" />;

            // Style lines that start with [SourceName]
            const bracketMatch = line.match(/^\[(.+?)\]\s*(.*)$/);
            if (bracketMatch && !isUser) {
              return (
                <p key={i} className="mb-1.5">
                  <span className="font-semibold text-brand">[{bracketMatch[1]}]</span>{' '}
                  <span className="text-text-muted">{renderInline(bracketMatch[2])}</span>
                </p>
              );
            }

            // Style numbered list items
            const numberedMatch = line.match(/^\[(\d+)\]\s*(.*)$/);
            if (numberedMatch && !isUser) {
              return (
                <p key={i} className="mb-1.5">
                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-brand/10 text-brand text-[10px] font-bold mr-1.5">{numberedMatch[1]}</span>
                  <span className="text-text-muted">{renderInline(numberedMatch[2])}</span>
                </p>
              );
            }

            // Style dash-prefixed items
            const dashMatch = line.match(/^—\s*(.*)$/);
            if (dashMatch && !isUser) {
              return (
                <p key={i} className="mb-1 pl-3 relative text-text-muted">
                  <span className="absolute left-0 top-0 text-brand/30">—</span>
                  {renderInline(dashMatch[1])}
                </p>
              );
            }

            return <p key={i} className="mb-1.5 last:mb-0">{renderInline(line)}</p>;
          })}
        </div>

        {/* Confidence + Review + Capability + Feedback row (NFCU-only when confidence present) */}
        {!isUser && (confidence || (capability && onCapabilityClick)) && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {confidence && <ConfidenceTierBadge confidence={confidence} />}
            {confidence?.review && <ReviewBadge review={confidence.review} />}
            {capability && onCapabilityClick && (
              <CapabilityBadge capability={capability} onClick={onCapabilityClick} />
            )}
            {confidence && (
              <MessageFeedback
                messageId={message.id}
                flowKey={message.flowKey}
                persona={persona.id}
                modelVersion={confidence.model_version}
              />
            )}
          </div>
        )}

        {/* Escalation banner — only when confidence < threshold */}
        {!isUser && confidence?.escalation?.triggered && (
          <EscalationNotice
            confidence={confidence}
            flowKey={message.flowKey}
            persona={persona}
          />
        )}

        {/* Inline components */}
        {inlineComponents && inlineComponents.length > 0 && (
          <div className="mt-3 space-y-3">
            {inlineComponents.map((comp, idx) => (
              <VizErrorBoundary key={idx}>{comp}</VizErrorBoundary>
            ))}
          </div>
        )}

        {/* Source badges */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-2.5 pl-0.5">
            <div className="flex flex-wrap gap-1.5">
              {message.sources.map((source, idx) => (
                <SourceBadge key={idx} source={source} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* User avatar */}
      {isUser && !compact && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-bg to-border flex items-center justify-center flex-shrink-0 mt-0.5 border border-border/60">
          <span className="text-text-muted text-[10px] font-bold">{persona.initials}</span>
        </div>
      )}
    </motion.div>
  );
}
