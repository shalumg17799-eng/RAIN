import type { ReactNode } from 'react';

/** Small building blocks shared by tenant card kits: a status pill, a group label and a key-points list. */

export type Tone = 'good' | 'warning' | 'critical' | 'info' | 'neutral' | 'brand';

const TONE: Record<Tone, string> = {
  good: 'border-success/30 bg-success-subtle text-success-700',
  warning: 'border-warning/30 bg-warning-subtle text-warning-700',
  critical: 'border-critical/30 bg-critical-subtle text-critical-700',
  info: 'border-info/30 bg-info-subtle text-info-700',
  neutral: 'border-border bg-surface-2 text-text-muted',
  brand: 'border-brand/25 bg-brand/10 text-brand',
};

export function Pill({ tone = 'neutral', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold ${TONE[tone]}${className ? ` ${className}` : ''}`}>{children}</span>;
}

/** A small uppercase label above a group inside a card. */
export function GroupLabel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <p className={`mb-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-text-subtle ${className}`}>{children}</p>;
}

/** The rest of an answer, under the card's title (house rule: one sentence in the bubble). */
export function KeyPoints({ points }: { points?: string[] }) {
  if (!points?.length) return null;
  return (
    <ul className="mb-3 space-y-1.5 rounded-xl bg-surface-2/70 px-3.5 py-2.5 text-[13px] leading-relaxed text-text">
      {points.map((p) => (
        <li key={p} className="flex gap-2">
          <span aria-hidden="true" className="mt-[7px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-brand" />
          <span>{p}</span>
        </li>
      ))}
    </ul>
  );
}
