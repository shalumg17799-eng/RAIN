/**
 * Named datasets the persona contracts reference by id (spec: "steps reference
 * data by ID only"). Each is the props of a catalog component (chart,
 * data_table, grid), served ready-made by the backend (GET /api/v4/ui/data →
 * section "datasets"), so no contract or component changes when the data does.
 */
import { rainSection, rainValue } from './backendData';

type Props = Record<string, unknown>;

export const DATASETS: Record<string, () => Props> = Object.fromEntries(
  Object.keys(rainSection('datasets')).map((name) => [name, () => rainValue<Props>('datasets', name)]),
);
