import { Sparkles, ChevronRight } from 'lucide-react';

export default function CapabilityBadge({ capability, onClick }) {
  if (!capability) return null;

  // Static, non-clickable info pill (no chevron, no hover, no cursor) for personas
  // that opt out of the capability deep-dive via features.staticCapabilityBadges.
  if (capability.interactive === false) {
    return (
      <span
        data-capability-badge={capability.capabilityName}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-brand/[0.06] to-brand/[0.03] border border-brand/10"
      >
        <Sparkles className="w-3 h-3 text-brand/50" />
        <span className="text-[11px] font-semibold text-brand/80">{capability.capabilityName}</span>
      </span>
    );
  }

  return (
    <button
      onClick={() => onClick(capability)}
      data-capability-badge={capability.capabilityName}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-brand/[0.06] to-brand/[0.03] border border-brand/10 hover:border-brand/20 hover:from-brand/[0.1] hover:to-brand/[0.06] transition-all duration-200 cursor-pointer group"
    >
      <Sparkles className="w-3 h-3 text-brand/50 group-hover:text-brand/70" />
      <span className="text-[11px] font-semibold text-brand/80 group-hover:text-brand">
        {capability.capabilityName}
      </span>
      <ChevronRight className="w-3 h-3 text-brand/30 group-hover:text-brand/60 group-hover:translate-x-0.5 transition-all" />
    </button>
  );
}
