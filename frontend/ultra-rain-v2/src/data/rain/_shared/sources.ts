/**
 * RAIN's data foundation for the Data Sources workbench: the public sources,
 * the labelled synthetic datasets, and the RAIN engines that read them. Served
 * by the backend (GET /api/v4/ui2/data → section "sources"); the record counts of
 * the public sources loaded in rain_v4.public_data are live row counts
 * (`live: true`, with the backing `table`).
 */
import type { DataSource } from '@core/types';
import { rainValue } from './backendData';

export type SourceKind = 'Public' | 'Synthetic' | 'Engine';

export interface RainSource extends DataSource {
  kind: SourceKind;
  provides: string;
  usedFor: string;
  freshness: string;
  recordCount: number;
  /** True when recordCount is a live row count from the backend's public_data tables. */
  live?: boolean;
  /** The backend table behind a live count. */
  table?: string;
}

export const PUBLIC_SOURCES = rainValue<RainSource[]>('sources', 'PUBLIC_SOURCES');
export const SYNTHETIC_SOURCES = rainValue<RainSource[]>('sources', 'SYNTHETIC_SOURCES');
export const ENGINES = rainValue<RainSource[]>('sources', 'ENGINES');

export const ALL_SOURCES: RainSource[] = [...PUBLIC_SOURCES, ...SYNTHETIC_SOURCES, ...ENGINES];
