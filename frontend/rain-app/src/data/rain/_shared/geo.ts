/**
 * Map geometry for RAIN's county maps: the state, the six network counties,
 * the seven sites and the frontier places (simplified lon/lat polygons, drawn
 * as inline SVG; illustrative shapes near the real ones, not legal boundaries).
 * The shapes come from the backend (GET /api/v4/ui/data → section "geo");
 * this module keeps only the projection math.
 */
import type { CountyId } from './constants';
import { rainValue } from './backendData';

type LonLat = [number, number];
const G = <T,>(key: string) => rainValue<T>('geo', key);

export const STATE_OUTLINE = G<LonLat[]>('STATE_OUTLINE');

export const COUNTY_SHAPES = G<Record<CountyId, LonLat[]>>('COUNTY_SHAPES');

/** Where each county's label sits. */
export const COUNTY_LABEL = G<Record<CountyId, LonLat>>('COUNTY_LABEL');

export const SITE_POINTS = G<Record<string, LonLat>>('SITE_POINTS');

/** Neighbouring counties outside the network, drawn neutral so the map reads as whole. */
export const OTHER_COUNTIES = G<Array<{ name: string; shape: LonLat[]; label: LonLat }>>('OTHER_COUNTIES');

/**
 * Frontier places (by town, not ZIP code). The first six are the low-broadband
 * areas. `side` puts the label left of the dot near the east edge; `dy` moves
 * it down where two labels would touch.
 */
export const FRONTIER_POINTS = G<Array<{ name: string; at: LonLat; county: CountyId; lowBroadband: boolean; side?: 'left' | 'right'; dy?: number }>>('FRONTIER_POINTS');

/** The view box the maps project into: the north and centre of the state, with a margin for labels. */
export const VIEW = G<{ readonly minLon: number; readonly maxLon: number; readonly minLat: number; readonly maxLat: number }>('VIEW');

const K = Math.cos((40.3 * Math.PI) / 180);

/** lon/lat → SVG x/y inside a `width`-wide frame. */
export function project([lon, lat]: LonLat, width: number) {
  const spanX = (VIEW.maxLon - VIEW.minLon) * K;
  const scale = width / spanX;
  return { x: (lon - VIEW.minLon) * K * scale, y: (VIEW.maxLat - lat) * scale };
}

export function viewHeight(width: number) {
  const spanX = (VIEW.maxLon - VIEW.minLon) * K;
  return ((VIEW.maxLat - VIEW.minLat) * width) / spanX;
}

export function pathOf(points: LonLat[], width: number) {
  return `${points
    .map((p, i) => {
      const { x, y } = project(p, width);
      return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ')} Z`;
}
