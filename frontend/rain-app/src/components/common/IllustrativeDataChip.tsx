/**
 * IllustrativeDataChip + ProvenanceLine — the trust furniture.
 *
 * Every tenant whose chrome carries a real organisation's identity while its
 * numbers are invented needs to say so beside the numbers themselves, not only
 * on a disclosures screen nobody opens mid-demo:
 *   • IllustrativeDataChip — this figure is invented, not the client's data.
 *   • ProvenanceLine       — where the figure came from and how fresh it is.
 *
 * Lived under `components/aramco/` until AMISA needed the same furniture. It was
 * never Aramco-specific — only its default tooltip was — so it moved here rather
 * than being copied; the Oil & Gas importers now import it from here.
 */
import { Info } from 'lucide-react';

/**
 * Marks a figure as illustrative. `note` explains anything unusual (e.g. a KPI
 * that is deliberately unmeasured rather than invented).
 */
export interface IllustrativeDataChipProps {
  /** Explains anything unusual; replaces the default tooltip. */
  note?: string;
  size?: 'sm' | 'md';
  className?: string;
}

export default function IllustrativeDataChip({ note, size = 'md', className = '' }: IllustrativeDataChipProps) {
  const sizing = size === 'sm' ? 'text-[9px] px-1.5 py-0.5 gap-0.5' : 'text-[10px] px-2 py-0.5 gap-1';
  return (
    <span
      title={note || 'Illustrative figure — authored for this prototype, not the client\u2019s data.'}
      className={`inline-flex items-center rounded-full border border-border bg-surface-2 text-text-subtle font-medium whitespace-nowrap ${sizing} ${className}`}
    >
      <Info className={size === 'sm' ? 'w-2.5 h-2.5' : 'w-3 h-3'} />
      Illustrative data
    </span>
  );
}

/** Source + freshness, and optionally a reconciliation note, under a figure. */
export interface ProvenanceLineProps {
  source?: string;
  freshness?: string;
  reconciled?: boolean;
  note?: string;
  className?: string;
}

export function ProvenanceLine({ source, freshness, reconciled = false, note, className = '' }: ProvenanceLineProps) {
  if (!source && !freshness) return null;
  return (
    <p className={`text-[10px] text-text-subtle leading-snug ${className}`}>
      {source && (
        <>
          <span className="font-medium text-text-muted">Source:</span> {source}
        </>
      )}
      {source && freshness ? ' · ' : ''}
      {freshness && (
        <>
          <span className="font-medium text-text-muted">Updated:</span> {freshness}
        </>
      )}
      {reconciled && <span className="ml-1 font-semibold text-success-700">· Reconciled</span>}
      {note && <span className="block mt-0.5 italic">{note}</span>}
    </p>
  );
}
