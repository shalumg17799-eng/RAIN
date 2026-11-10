/**
 * Node scripts (fixtures, catalog, mock API) read RAIN data the way the app
 * does, from the backend: here, the backend's seed file, the one loaded into
 * rain_v3.ui_v3.dataset. Import this first, before anything that reads data.
 */
import { readFileSync } from 'node:fs';
import { hydrateRainData } from '../../src/data/rain/_shared/backendData';

hydrateRainData(
  JSON.parse(readFileSync(new URL('../../../../rain-api/seed/rain_v3_ui_data.json', import.meta.url), 'utf8')),
  'rain-api/seed/rain_v3_ui_data.json',
);
