/**
 * Simplified Nevada outlines for RAIN's county maps: the state, the six
 * network counties, the seven sites and the frontier places. Hand-simplified
 * lon/lat polygons, drawn as inline SVG (plan D16): illustrative shapes near
 * the real ones, not legal boundaries.
 */
import type { CountyId } from './constants';

type LonLat = [number, number];

export const STATE_OUTLINE: LonLat[] = [
  [-120.0, 42.0], [-114.04, 42.0], [-114.04, 36.2], [-114.63, 35.0], [-120.0, 39.0],
];

export const COUNTY_SHAPES: Record<CountyId, LonLat[]> = {
  humboldt: [[-119.33, 42.0], [-117.02, 42.0], [-117.02, 40.85], [-117.3, 40.52], [-118.78, 40.85], [-119.33, 40.95]],
  elko: [[-117.02, 42.0], [-114.04, 42.0], [-114.04, 40.12], [-116.0, 40.12], [-116.6, 40.6], [-117.02, 40.85]],
  lander: [[-117.3, 40.52], [-117.02, 40.85], [-116.6, 40.6], [-116.6, 38.75], [-117.25, 38.75], [-117.5, 39.15], [-117.55, 40.0]],
  pershing: [[-119.33, 40.95], [-118.78, 40.85], [-117.3, 40.52], [-117.55, 40.0], [-118.75, 39.95], [-119.33, 40.2]],
  churchill: [[-119.0, 39.92], [-117.55, 40.0], [-117.5, 39.15], [-117.85, 39.07], [-118.75, 39.05], [-119.2, 39.5]],
  whitePine: [[-115.83, 40.12], [-114.04, 40.12], [-114.04, 38.68], [-115.9, 38.68]],
};

/** Where each county's label sits. */
export const COUNTY_LABEL: Record<CountyId, LonLat> = {
  humboldt: [-118.2, 41.45],
  elko: [-115.5, 41.25],
  lander: [-117.0, 39.6],
  pershing: [-118.45, 40.45],
  churchill: [-118.3, 39.55],
  whitePine: [-114.95, 39.5],
};

export const SITE_POINTS: Record<string, LonLat> = {
  elko: [-115.76, 40.83],
  wells: [-114.96, 41.11],
  winnemucca: [-117.74, 40.97],
  battleMountain: [-116.93, 40.64],
  lovelock: [-118.47, 40.18],
  ely: [-114.89, 39.25],
  fallon: [-118.78, 39.47],
};

/** Neighbouring counties outside the network, drawn neutral so the map reads as whole. */
export const OTHER_COUNTIES: Array<{ name: string; shape: LonLat[]; label: LonLat }> = [
  { name: 'Washoe', shape: [[-120.0, 42.0], [-119.33, 42.0], [-119.33, 40.2], [-119.0, 39.92], [-119.2, 39.5], [-119.7, 39.3], [-120.0, 39.15]], label: [-119.67, 40.9] },
  { name: 'Eureka', shape: [[-116.6, 40.6], [-116.0, 40.12], [-115.83, 40.12], [-115.9, 38.68], [-116.6, 38.75]], label: [-116.2, 39.5] },
];

/**
 * Frontier places (by town, not ZIP code). The first six are the low-broadband
 * areas. `side` puts the label left of the dot near the east edge; `dy` moves
 * it down where two labels would touch.
 */
export const FRONTIER_POINTS: Array<{ name: string; at: LonLat; county: CountyId; lowBroadband: boolean; side?: 'left' | 'right'; dy?: number }> = [
  { name: 'Jarbidge', at: [-115.43, 41.87], county: 'elko', lowBroadband: true, dy: 14 },
  { name: 'Denio', at: [-118.63, 41.99], county: 'humboldt', lowBroadband: true },
  { name: 'Austin', at: [-117.07, 39.49], county: 'lander', lowBroadband: true },
  { name: 'Imlay', at: [-118.15, 40.66], county: 'pershing', lowBroadband: true },
  { name: 'Baker', at: [-114.14, 39.01], county: 'whitePine', lowBroadband: true, side: 'left' },
  { name: 'Owyhee', at: [-116.1, 41.95], county: 'elko', lowBroadband: true },
  { name: 'Jackpot', at: [-114.67, 41.98], county: 'elko', lowBroadband: false, side: 'left' },
  { name: 'McDermitt', at: [-117.72, 41.99], county: 'humboldt', lowBroadband: false },
];

/** The view box the maps project into: the north and centre of the state, with a margin for labels. */
export const VIEW = { minLon: -120.2, maxLon: -113.75, minLat: 38.45, maxLat: 42.3 } as const;

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
