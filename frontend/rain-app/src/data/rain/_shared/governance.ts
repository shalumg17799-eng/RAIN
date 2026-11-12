/**
 * The CIO's governance records: the subgroup check, the model features, the
 * 57 members who enter and leave the top 300, and the drive-time scatter.
 * Served by the backend (GET /api/v4/ui/data → section "governance").
 * De-identified; every person is fictional.
 */
import { rainValue } from './backendData';

/** Average risk rank (percentile, higher ranks first) by condition group, frontier vs town. */
export const SUBGROUP = rainValue<ReadonlyArray<{ readonly group: string; readonly town: number; readonly frontier: number; readonly frontierAfter: number }>>('governance', 'SUBGROUP');

export interface ModelFeature {
  id: string;
  name: string;
  weight: number;
  kind: 'Current' | 'Added in v1.4';
  note: string;
}

export const FEATURES = rainValue<ModelFeature[]>('governance', 'FEATURES');

export interface SwapRow {
  id: string;
  direction: 'Enters top 300' | 'Leaves top 300';
  condition: string;
  driveMin: number;
  rankBefore: number;
  rankAfter: number;
  inBpDenominator: boolean;
}

/** The 57 in and 57 out, de-identified (GET /models/impactability/swaps). */
export function getSwaps(): SwapRow[] {
  return rainValue<SwapRow[]>('governance', 'swaps');
}

/** Drive time against primary care visits, de-identified (GET /models/impactability/access). */
export function getAccessPoints(): Array<{ id: string; driveMin: number; visits: number; frontier: boolean }> {
  return rainValue('governance', 'accessPoints');
}
