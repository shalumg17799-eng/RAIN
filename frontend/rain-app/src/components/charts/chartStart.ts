/**
 * Recharts starts a responsive chart at -1 x -1 and prints a warning to the console
 * until its box is measured. In the browser the charts start at 1 x 1 instead, so the
 * console shows backend API calls only; under tests Recharts' default is kept so the
 * rendering (and the snapshots) stay deterministic.
 */
export const CHART_START = import.meta.env.MODE === 'test' ? { width: -1, height: -1 } : { width: 1, height: 1 };
