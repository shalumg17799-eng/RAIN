/** Declarations split out of JourneyMap.tsx to keep it under 400 lines; behaviour unchanged. */


/** One phase of the journey. `emotion` is 1 (low) to 5 (high). */
export interface JourneyPhase {
  id: string;
  index: number;
  name: string;
  emotion: number;
  emotionLabel: string;
  touchpoints: string[];
  action: string;
  thought: string;
  painPoints: string[];
  opportunity: string;
  momentOfTruth?: boolean;
  momentLabel?: string;
  demoStep?: string;
  flowKey?: string;
  /** Optional future-state emotion, drawn as a dashed line. */
  futureEmotion?: number;
}

export interface Journey {
  scenario: string;
  timeframe: string;
  baselineSatisfaction: number;
  baselineScale?: number;
  baselineNote: string;
  illustrative?: boolean;
  phases: JourneyPhase[];
  /** Optional future-state overlay copy. */
  futureLabel?: string;
  futureNote?: string;
  traceability?: Array<{ phase: string; painPoint: string; signal: string; signalId?: string; demoStep?: string }>;
}

export type Point = [number, number];
