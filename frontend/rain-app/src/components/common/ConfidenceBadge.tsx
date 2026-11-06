import { tierFor, colorFor, bgFor, borderFor, labelFor } from '@/utils/confidence';

/**
 * "AI Confidence: 94%" — the pill that sits on every consequential card.
 *
 * Generic across tenants: the colours come from Ultra's confidence helpers, so
 * it follows whichever brand's confHigh/confMed/confLow tokens are active
 * rather than hardcoding a green. Lived in `components/doit/shared/TrustBits`
 * until AMISA needed it too; that module re-exports it, so the DoIT cards that
 * import it from there did not have to change.
 *
 * These are authored scores, not model output. The point they make is that a
 * consequential number arrives with a number attached to how much to trust it.
 */
export interface ConfidenceBadgeProps {
  /** 0–100. */
  score: number;
  /** Tooltip; defaults to the tier's name. */
  note?: string;
}

export default function ConfidenceBadge({ score, note }: ConfidenceBadgeProps) {
  const tier = tierFor(score);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold"
      style={{ color: colorFor(tier), background: bgFor(tier), borderColor: borderFor(tier) }}
      title={note || `${labelFor(tier)} confidence`}
    >
      <span aria-hidden="true">◉</span>
      AI Confidence: {score}%
    </span>
  );
}
