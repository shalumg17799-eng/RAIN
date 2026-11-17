/**
 * Node scripts (catalog, mock API, contract inference) read RAIN data the way
 * the app does, from the backend: by default the seed-built snapshot of
 * GET /api/v4/ui2/data the unit tests use (src/test/fixtures/rain_v4_ui2_data.json),
 * or another snapshot named by RAIN_DATA_SNAPSHOT (e.g. the live one that
 * `npm run fixtures:backend` writes). Import this first, before anything that reads data.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { hydrateRainData } from '../../src/data/rain/_shared/backendData';

const file = process.env.RAIN_DATA_SNAPSHOT
  ? resolve(process.env.RAIN_DATA_SNAPSHOT)
  : new URL('../../src/test/fixtures/rain_v4_ui2_data.json', import.meta.url);

hydrateRainData(JSON.parse(readFileSync(file, 'utf8')), `${String(file)} (snapshot of /api/v4/ui2/data)`);
