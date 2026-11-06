import { useEffect, useState, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { tierFor, colorFor, labelFor } from '@/utils/confidence';

export default function ConfidencePopover({ confidence, anchorRef, onClose }) {
  const [pos, setPos] = useState(null);

  useLayoutEffect(() => {
    if (!anchorRef?.current) return;
    const rect = anchorRef.current.getBoundingClientRect();
    const POPOVER_W = 340;
    const left = Math.min(
      Math.max(8, rect.left),
      window.innerWidth - POPOVER_W - 8
    );
    setPos({ top: rect.bottom + 8, left });
  }, [anchorRef]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    const onClick = (e) => {
      if (anchorRef?.current?.contains(e.target)) return;
      const popover = document.getElementById('confidence-popover');
      if (popover?.contains(e.target)) return;
      onClose();
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, [onClose, anchorRef]);

  if (!pos) return null;

  const tier = tierFor(confidence.score);
  const color = colorFor(tier);
  const validatedAt = confidence.validated_at
    ? new Date(confidence.validated_at).toLocaleString(undefined, {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      })
    : null;

  return createPortal(
    <AnimatePresence>
      <motion.div
        id="confidence-popover"
        initial={{ opacity: 0, scale: 0.96, y: 4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 4 }}
        transition={{ duration: 0.18, ease: 'easeOut' }}
        style={{ position: 'fixed', top: pos.top, left: pos.left, width: 340, zIndex: 60 }}
        className="bg-surface rounded-xl border border-border shadow-[0_8px_28px_rgba(0,0,0,0.12)] overflow-hidden"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: color }} />
            <div>
              <div className="text-xs font-bold text-text leading-tight">
                Confidence {confidence.score}% — {labelFor(tier)}
              </div>
              <div className="text-[10px] text-text-muted">
                Threshold {confidence.threshold ?? 70}% · auto-escalate below
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-text-subtle hover:text-text-muted cursor-pointer">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="px-4 py-3 space-y-3">
          {confidence.rationale && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-text-subtle font-bold mb-1">Rationale</div>
              <p className="text-xs text-text-muted leading-relaxed">{confidence.rationale}</p>
            </div>
          )}

          {Array.isArray(confidence.feature_contributions) && confidence.feature_contributions.length > 0 ? (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-text-subtle font-bold mb-1.5">Evidence Trace</div>
              <ul className="space-y-1.5">
                {[...confidence.feature_contributions]
                  .sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0))
                  .map((c, i) => {
                    const w = Math.max(0, Math.min(1, c.weight ?? 0));
                    const barColor = w >= 0.25 ? 'var(--color-success)' : w >= 0.10 ? 'var(--color-brand)' : 'var(--color-text-subtle)';
                    return (
                      <li key={i} className="space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          {c.source && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-brand/[0.08] text-[10px] font-medium text-brand flex-shrink-0">
                              {c.source}
                            </span>
                          )}
                          <span className="font-mono text-[10.5px] text-text-muted truncate">{c.feature}</span>
                          <span className="ml-auto font-mono text-[10px] tabular-nums text-text-muted flex-shrink-0">
                            {w.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full bg-surface-2 overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{ width: `${w * 100}%`, background: barColor }}
                            />
                          </div>
                        </div>
                        {c.value && (
                          <div className="text-[10.5px] text-text-muted pl-0.5 leading-snug">{c.value}</div>
                        )}
                      </li>
                    );
                  })}
              </ul>
            </div>
          ) : (
            Array.isArray(confidence.signals_used) && confidence.signals_used.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wider text-text-subtle font-bold mb-1">Grounded in</div>
                <div className="flex flex-wrap gap-1.5">
                  {confidence.signals_used.map((src, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center px-2 py-0.5 rounded-md bg-brand/[0.08] text-[10px] font-medium text-brand"
                    >
                      {src}
                    </span>
                  ))}
                </div>
              </div>
            )
          )}

          <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border-subtle">
            {confidence.model_version && (
              <div>
                <div className="text-[10px] uppercase tracking-wider text-text-subtle font-bold">Model</div>
                <div className="text-[11px] font-mono text-text-muted">{confidence.model_version}</div>
              </div>
            )}
            {validatedAt && (
              <div>
                <div className="text-[10px] uppercase tracking-wider text-text-subtle font-bold">Validated</div>
                <div className="text-[11px] text-text-muted">{validatedAt}</div>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
