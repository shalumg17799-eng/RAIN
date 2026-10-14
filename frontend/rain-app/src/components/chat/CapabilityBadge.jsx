import { Sparkles, ChevronRight } from 'lucide-react';

export default function CapabilityBadge({ capability, onClick }) {
  if (!capability) return null;

  return (
    <button
      onClick={() => onClick(capability)}
      data-capability-badge={capability.capabilityName}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-[#003087]/[0.06] to-[#003087]/[0.03] border border-[#003087]/10 hover:border-[#003087]/20 hover:from-[#003087]/[0.1] hover:to-[#003087]/[0.06] transition-all duration-200 cursor-pointer group"
    >
      <Sparkles className="w-3 h-3 text-[#003087]/50 group-hover:text-[#003087]/70" />
      <span className="text-[11px] font-semibold text-[#003087]/80 group-hover:text-[#003087]">
        {capability.capabilityName}
      </span>
      <ChevronRight className="w-3 h-3 text-[#003087]/30 group-hover:text-[#003087]/60 group-hover:translate-x-0.5 transition-all" />
    </button>
  );
}
