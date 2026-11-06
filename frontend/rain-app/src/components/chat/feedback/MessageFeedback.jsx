import { useState, useEffect, useId } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ThumbsUp, ThumbsDown, Check, X, Sparkles } from 'lucide-react';
import { backdrop, focusOnMount } from '@core/a11y';
import { EVENTS } from '@core/contract/events';
import { STORAGE_KEYS } from '@core/contract/storageKeys';
import { nowIso } from '@core/clock';

const STORAGE_KEY = STORAGE_KEYS.messageFeedback;

function loadAll() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function saveOne(messageId, entry) {
  try {
    const all = loadAll();
    all[messageId] = entry;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(all));
  } catch {
    /* noop */
  }
}

function broadcastEvent(detail) {
  try {
    window.dispatchEvent(new CustomEvent(EVENTS.nfcuFeedback, { detail }));
  } catch {
    /* noop */
  }
}

export default function MessageFeedback({ messageId, flowKey, persona, modelVersion }) {
  // Hydrated from sessionStorage on first render, and again if the message changes.
  const [feedback, setFeedback] = useState(() => loadAll()[messageId] ?? null);
  const [hydratedFor, setHydratedFor] = useState(messageId);
  if (messageId !== hydratedFor) {
    setHydratedFor(messageId);
    const stored = loadAll()[messageId];
    if (stored) setFeedback(stored);
  }
  const [showPopover, setShowPopover] = useState(false);
  const [comment, setComment] = useState('');
  const commentId = useId();

  // Close modal on Escape
  useEffect(() => {
    if (!showPopover) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setShowPopover(false);
        setComment('');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showPopover]);

  const submitPositive = () => {
    const entry = {
      messageId,
      sentiment: 'positive',
      comment: null,
      timestamp: nowIso(),
      flowKey,
      persona,
      modelVersion,
    };
    saveOne(messageId, entry);
    setFeedback(entry);
    broadcastEvent(entry);
  };

  const submitNegative = () => {
    const entry = {
      messageId,
      sentiment: 'negative',
      comment: comment.trim() || null,
      timestamp: nowIso(),
      flowKey,
      persona,
      modelVersion,
    };
    saveOne(messageId, entry);
    setFeedback(entry);
    setShowPopover(false);
    setComment('');
    broadcastEvent(entry);
  };

  // Submitted state — replace the icon buttons with a confirmation chip
  if (feedback) {
    const isPositive = feedback.sentiment === 'positive';
    return (
      <motion.span
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2 }}
        className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
          isPositive
            ? 'text-success-800 bg-success-50 border border-success-200'
            : 'text-warning-800 bg-warning-50 border border-warning-200'
        }`}
        title={
          isPositive
            ? 'Helpful — logged for model refinement'
            : feedback.comment
              ? `Logged: "${feedback.comment}"`
              : 'Logged — flagged for review'
        }
      >
        <Check className="w-3 h-3" />
        <span>{isPositive ? 'Feedback recorded' : 'Feedback flagged'}</span>
        {!isPositive && feedback.comment && (
          <Sparkles className="w-3 h-3 opacity-70" />
        )}
      </motion.span>
    );
  }

  return (
    <div className="relative inline-flex items-center gap-0.5">
      <button
        type="button"
        onClick={submitPositive}
        title="Helpful — log this response as good"
        aria-label="Mark response as helpful"
        className="inline-flex items-center justify-center w-6 h-6 rounded-full text-text-subtle hover:text-success-800 hover:bg-success-50 active:scale-95 transition-all cursor-pointer"
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        onClick={() => setShowPopover((v) => !v)}
        title="Needs improvement — leave a comment"
        aria-label="Mark response as needing improvement"
        className={`inline-flex items-center justify-center w-6 h-6 rounded-full transition-all cursor-pointer active:scale-95 ${
          showPopover
            ? 'text-critical-800 bg-critical-50'
            : 'text-text-subtle hover:text-critical-800 hover:bg-critical-50'
        }`}
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>

      {showPopover && createPortal(
        <AnimatePresence>
          <motion.div
            key="feedback-modal-root"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-black/45"
              {...backdrop(() => { setShowPopover(false); setComment(''); })}
            />

            {/* Card */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
              className="relative w-full max-w-[560px] bg-surface rounded-2xl overflow-hidden"
              style={{ boxShadow: '0 24px 64px rgba(0,0,0,0.25)' }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-start justify-between px-6 pt-5 pb-4 border-b border-border-subtle">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-critical-50 flex items-center justify-center flex-shrink-0">
                    <ThumbsDown className="w-4 h-4 text-critical-600" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-[15px] font-bold text-text leading-tight">Give feedback on this response</h3>
                    <p className="text-[12px] text-text-muted mt-1 leading-relaxed">
                      Tell us what was off — your context goes into the model-refinement queue tagged with the persona, flow, and model version.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => { setShowPopover(false); setComment(''); }}
                  className="text-text-subtle hover:text-text-muted cursor-pointer flex-shrink-0 ml-2"
                  aria-label="Close feedback form"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Body */}
              <div className="px-6 py-5 space-y-3.5">
                <div>
                  <label htmlFor={commentId} className="text-[10px] uppercase tracking-wider font-bold text-text-muted mb-1.5 block">
                    What was wrong or missing?
                  </label>
                  <textarea
                    id={commentId}
                    ref={focusOnMount}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="e.g. The reroute estimate looks aggressive for evening volume. We'd want callback enabled before agent moves. Or: the source for the historical pattern feels stale — please use the last 90 days only."
                    className="w-full text-[13px] text-text placeholder:text-text-subtle border border-border rounded-lg p-3 h-36 resize-none focus:outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 leading-relaxed"
                  />
                </div>
                <div className="flex items-start gap-2 text-[11px] text-text-muted leading-relaxed">
                  <Sparkles className="w-3.5 h-3.5 text-brand/70 flex-shrink-0 mt-0.5" />
                  <span>
                    Logged for the next model retrain. The audit trail captures persona, flow, model version, and timestamp alongside your comment so future reviews can trace back to this moment.
                  </span>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-2 px-6 py-3.5 bg-surface-2 border-t border-border-subtle">
                <button
                  onClick={() => { setShowPopover(false); setComment(''); }}
                  className="text-[13px] font-medium text-text-muted px-4 py-2 rounded-lg hover:bg-surface-2 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={submitNegative}
                  className="text-[13px] font-semibold text-white bg-brand hover:bg-brand/90 px-4 py-2 rounded-lg cursor-pointer transition-colors"
                >
                  Submit feedback
                </button>
              </div>
            </motion.div>
          </motion.div>
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}
