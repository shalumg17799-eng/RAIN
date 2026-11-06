import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, X, FileSignature } from 'lucide-react';

const statusConfig = {
  resolved:  { Icon: CheckCircle2,  label: 'Reviewed',  color: 'var(--color-success)', bg: 'color-mix(in srgb, var(--color-success) 10%, transparent)',  border: 'color-mix(in srgb, var(--color-success) 25%, transparent)' },
  approved:  { Icon: CheckCircle2,  label: 'Approved',  color: 'var(--color-success)', bg: 'color-mix(in srgb, var(--color-success) 10%, transparent)',  border: 'color-mix(in srgb, var(--color-success) 25%, transparent)' },
  overridden:{ Icon: FileSignature, label: 'Overridden',color: 'var(--color-warning)', bg: 'color-mix(in srgb, var(--color-warning) 10%, transparent)',  border: 'color-mix(in srgb, var(--color-warning) 25%, transparent)' },
  audited:   { Icon: CheckCircle2,  label: 'Audited',   color: 'var(--color-brand)', bg: 'color-mix(in srgb, var(--color-brand) 8%, transparent)',   border: 'color-mix(in srgb, var(--color-brand) 20%, transparent)' },
};

function fmtTime(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch { return null; }
}

export default function ReviewBadge({ review }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  if (!review || !review.reviewer) return null;
  const cfg = statusConfig[review.status] || statusConfig.resolved;
  const Icon = cfg.Icon;
  const ts = fmtTime(review.reviewed_at);

  return (
    <div className="relative">
      <button
        ref={ref}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold transition-colors cursor-pointer"
        style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}
      >
        <Icon className="w-3 h-3" />
        <span>{cfg.label} by {review.reviewer}</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18 }}
            className="absolute top-full mt-2 left-0 z-30 w-[300px] bg-surface rounded-xl border border-border p-3.5"
            style={{ boxShadow: '0 8px 28px rgba(0,0,0,0.12)' }}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="text-[11px] font-bold text-text">Human Review Captured</div>
                <div className="text-[10px] text-text-muted">{cfg.label.toLowerCase()} by a designated reviewer</div>
              </div>
              <button onClick={() => setOpen(false)} className="text-text-subtle hover:text-text-muted cursor-pointer">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between gap-2">
                <span className="text-[10px] uppercase tracking-wider font-bold text-text-subtle">Reviewer</span>
                <span className="text-[11px] font-semibold text-text text-right">{review.reviewer}</span>
              </div>
              {review.reviewer_role && (
                <div className="flex justify-between gap-2">
                  <span className="text-[10px] uppercase tracking-wider font-bold text-text-subtle">Role</span>
                  <span className="text-[11px] text-text-muted text-right">{review.reviewer_role}</span>
                </div>
              )}
              {ts && (
                <div className="flex justify-between gap-2">
                  <span className="text-[10px] uppercase tracking-wider font-bold text-text-subtle">Reviewed at</span>
                  <span className="text-[11px] text-text-muted text-right">{ts}</span>
                </div>
              )}
              {review.audit_id && (
                <div className="flex justify-between gap-2 pt-1.5 border-t border-border-subtle">
                  <span className="text-[10px] uppercase tracking-wider font-bold text-text-subtle">Audit</span>
                  <span className="text-[11px] font-mono text-brand text-right">{review.audit_id}</span>
                </div>
              )}
              {review.note && (
                <p className="text-[11px] text-text-muted leading-relaxed pt-1.5 border-t border-border-subtle">{review.note}</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
