/**
 * The turn's follow-up chips above the input, the recommended one highlighted.
 * Split out of PersonaWorkspace.jsx to keep it under 400 lines.
 */
import { ArrowRight } from 'lucide-react';

export default function FollowUpChips({ chips, recommendedChip, onChipClick, isPanel, compactOnMobile }) {
  return (
  // In a side panel the chips would otherwise push the thread out of view.
  <div
    className={
      isPanel
        ? 'scrollbar-sleek mb-2.5 max-h-[132px] overflow-y-auto'
        : compactOnMobile
          ? 'scrollbar-sleek mb-2.5 max-lg:max-h-[116px] max-lg:overflow-y-auto'
          : 'mb-2.5'
    }
  >
    <div className="flex flex-wrap gap-1.5">
      {chips.map((chip, idx) => {
        const isRecommended = chip === recommendedChip;
        return (
          <button
            key={idx}
            onClick={() => onChipClick(chip)}
            className={`group relative px-3.5 py-1.5 rounded-full text-[11px] font-medium border transition-all duration-200 cursor-pointer ${
              isRecommended
                ? 'bg-brand text-white border-brand hover:bg-brand-hover shadow-[0_2px_8px_color-mix(in_srgb,var(--color-brand)_30%,transparent)]'
                : 'border-border text-text-muted bg-surface hover:bg-surface-2 hover:border-brand/30 hover:text-brand shadow-sm hover:shadow'
            }`}
          >
            <span className="flex items-center gap-1.5">
              {isRecommended && <ArrowRight className="w-3 h-3" />}
              {chip}
            </span>
          </button>
        );
      })}
    </div>
  </div>
  );
}
