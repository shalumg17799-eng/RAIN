import { useState } from 'react';
import { motion } from 'framer-motion';
import { UserCheck, Check, Pencil, X, Loader2 } from 'lucide-react';

// Shown while the governed run is paused at the HITL gate: the reviewer approves, edits the
// narrative, or rejects — or the run times out server-side to an honest "could not verify".
export default function HitlReviewBar({ request, onDecide }) {
  const [editing, setEditing] = useState(false);
  const [narrative, setNarrative] = useState('');
  const [busy, setBusy] = useState(false);
  if (!request) return null;

  const decide = async (action, edited) => {
    setBusy(true);
    try {
      await onDecide(action, edited);
    } finally {
      setBusy(false);
      setEditing(false);
    }
  };

  const reasonText = {
    low_confidence: 'the answer is below the confidence threshold',
    governance_flag: 'a governance flag fired (masked columns or a failed source)',
    sensitive_intent: 'the question was screened as sensitive',
    forced: 'review was requested for this question',
  }[request.reason] || request.reason;

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="ml-11 mr-4 my-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
    >
      <div className="flex items-center gap-2 text-[12px] font-semibold text-amber-800">
        <UserCheck className="w-4 h-4 animate-pulse" />
        Human review requested — {reasonText}. Without a decision the answer times out as
        &ldquo;could not be verified&rdquo;.
      </div>
      {editing ? (
        <div className="mt-2">
          <textarea
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            placeholder="Write the narrative the user should see…"
            className="w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-[12px] text-gray-800 focus:outline-none focus:border-amber-400"
            rows={3}
          />
          <div className="flex gap-2 mt-1.5">
            <button disabled={busy || !narrative.trim()} onClick={() => decide('edit', narrative.trim())}
              className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-[11px] font-semibold bg-amber-600 text-white disabled:opacity-40">
              {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Pencil className="w-3 h-3" />} Send edit
            </button>
            <button disabled={busy} onClick={() => setEditing(false)}
              className="px-3 py-1 rounded-lg text-[11px] font-semibold border border-amber-300 text-amber-700">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2 mt-2">
          <button disabled={busy} onClick={() => decide('approve')}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-[11px] font-semibold bg-emerald-600 text-white disabled:opacity-40">
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />} Approve
          </button>
          <button disabled={busy} onClick={() => setEditing(true)}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-[11px] font-semibold border border-amber-300 text-amber-700">
            <Pencil className="w-3 h-3" /> Edit
          </button>
          <button disabled={busy} onClick={() => decide('reject')}
            className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-[11px] font-semibold border border-red-200 text-red-600">
            <X className="w-3 h-3" /> Reject
          </button>
        </div>
      )}
    </motion.div>
  );
}
