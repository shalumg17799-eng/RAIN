import PrioritySignalCards, { type PrioritySignalCardsProps } from '@/components/briefing/PrioritySignalCards';

/**
 * The three priority signal cards on a Use Case A briefing (spec "Priority
 * signals"): severity, the signal, its detail and sources. Clicking a card
 * asks its question. The shared priority signal cards, with the synthetic-data
 * label on the source line (spec: "Label synthetic data on every screen") and
 * the chip's question as the action line.
 */
export default function ValueBasedCareSignals(props: Omit<PrioritySignalCardsProps, 'sourceSuffix' | 'actionLine'>) {
  return <PrioritySignalCards {...props} sourceSuffix=" · Synthetic" actionLine="chip" />;
}
