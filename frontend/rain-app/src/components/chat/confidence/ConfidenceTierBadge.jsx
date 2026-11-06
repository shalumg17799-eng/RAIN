import { useState, useRef } from 'react';
import { ShieldCheck } from 'lucide-react';
import { tierFor, colorFor, bgFor, borderFor, labelFor } from '@/utils/confidence';
import ConfidencePopover from './ConfidencePopover';

export default function ConfidenceTierBadge({ confidence, compact = false }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);

  if (!confidence || typeof confidence.score !== 'number') return null;

  const tier = tierFor(confidence.score);
  const color = colorFor(tier);
  const bg = bgFor(tier);
  const border = borderFor(tier);

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold transition-colors cursor-pointer"
        style={{ background: bg, color, border: `1px solid ${border}` }}
      >
        <span className="inline-block w-1.5 h-1.5 rounded-full" style={{ background: color }} />
        <ShieldCheck className="w-3 h-3" />
        <span>
          {compact ? `${confidence.score}%` : `Confidence ${confidence.score}% · ${labelFor(tier)}`}
        </span>
      </button>

      {open && (
        <ConfidencePopover
          confidence={confidence}
          anchorRef={anchorRef}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
