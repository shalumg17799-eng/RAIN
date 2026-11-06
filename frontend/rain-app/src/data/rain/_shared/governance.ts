/**
 * The CIO's governance records: the subgroup check, the model features, the
 * 57 members who enter and leave the top 300, and the drive-time scatter.
 * Generated from fixed seeds and de-identified. Every person is fictional.
 */
import { MODEL } from './constants';
import { seeded } from './seeded';

// ─── CIO: subgroup check ────────────────────────────────────────────────────

/** Average risk rank (percentile, higher ranks first) by condition group, frontier vs town. */
export const SUBGROUP = [
  { group: 'Hypertension', town: 62, frontier: 51, frontierAfter: 60 },
  { group: 'Diabetes', town: 66, frontier: 54, frontierAfter: 64 },
  { group: 'COPD or asthma', town: 58, frontier: 48, frontierAfter: 56 },
  { group: 'Heart failure', town: 74, frontier: 61, frontierAfter: 72 },
  { group: 'Depression', town: 55, frontier: 45, frontierAfter: 53 },
] as const;

export interface ModelFeature {
  id: string;
  name: string;
  weight: number;
  kind: 'Current' | 'Added in v1.4';
  note: string;
}

export const FEATURES: ModelFeature[] = [
  { id: 'cost', name: 'Prior-year allowed cost', weight: 0.24, kind: 'Current', note: 'Reads thin claims history as low risk; the main source of the frontier gap.' },
  { id: 'pcVisits', name: 'Primary care visits, last 12 months', weight: 0.17, kind: 'Current', note: 'Frontier members have 31% fewer visits because sites are far, not because they are healthier.' },
  { id: 'ed', name: 'ED visits, last 12 months', weight: 0.14, kind: 'Current', note: 'Trails reality by the 45-day claims lag; ADT alerts would close it.' },
  { id: 'conditions', name: 'Chronic condition count', weight: 0.13, kind: 'Current', note: 'Clinical signal; behaves the same in town and frontier.' },
  { id: 'labs', name: 'Latest BP and HbA1c', weight: 0.12, kind: 'Current', note: 'Clinical signal; behaves the same in town and frontier.' },
  { id: 'gaps', name: 'Open care gaps', weight: 0.08, kind: 'Current', note: 'Counts gaps the EHR can see.' },
  { id: 'drive', name: 'Drive time to nearest site', weight: 0.05, kind: 'Added in v1.4', note: 'OpenStreetMap road network from the member ZIP centroid.' },
  { id: 'broadband', name: 'Broadband available for video', weight: 0.03, kind: 'Added in v1.4', note: 'FCC National Broadband Map at the member location.' },
  { id: 'missed', name: 'Missed appointments', weight: 0.02, kind: 'Added in v1.4', note: 'No-shows read as an access barrier, not low need.' },
  { id: 'hpsa', name: 'Shortage-area status', weight: 0.02, kind: 'Added in v1.4', note: 'HRSA primary care shortage area for the member county.' },
];

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
  const rnd = seeded(57057);
  const groups = ['Hypertension', 'Diabetes', 'Heart failure', 'COPD or asthma', 'Hypertension and diabetes'];
  const rows: SwapRow[] = [];
  for (let i = 0; i < MODEL.missingFromTop; i += 1) {
    rows.push({
      id: `F-${String(1000 + i * 13).padStart(4, '0')}`,
      direction: 'Enters top 300',
      condition: groups[Math.floor(rnd() * groups.length)],
      driveMin: 62 + Math.floor(rnd() * 70),
      rankBefore: 301 + Math.floor(rnd() * 380),
      rankAfter: 120 + Math.floor(rnd() * 180),
      inBpDenominator: i < MODEL.inBpDenominator,
    });
  }
  for (let i = 0; i < MODEL.missingFromTop; i += 1) {
    rows.push({
      id: `T-${String(2000 + i * 11).padStart(4, '0')}`,
      direction: 'Leaves top 300',
      condition: groups[Math.floor(rnd() * groups.length)],
      driveMin: 6 + Math.floor(rnd() * 30),
      rankBefore: 244 + Math.floor(rnd() * 56),
      rankAfter: 301 + Math.floor(rnd() * 60),
      inBpDenominator: false,
    });
  }
  return rows;
}

/** Drive time against primary care visits, de-identified (GET /models/impactability/access). */
export function getAccessPoints(): Array<{ id: string; driveMin: number; visits: number; frontier: boolean }> {
  const rnd = seeded(7474);
  const pts = [];
  for (let i = 0; i < 90; i += 1) {
    const frontier = i % 3 === 0;
    const driveMin = frontier ? 55 + Math.floor(rnd() * 80) : 5 + Math.floor(rnd() * 40);
    const visits = Math.max(0, Math.round((frontier ? 2.6 : 3.8) - driveMin / 60 + rnd() * 2.4));
    pts.push({ id: `P${i}`, driveMin, visits, frontier });
  }
  return pts;
}
