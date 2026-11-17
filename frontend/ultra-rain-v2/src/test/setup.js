import '@testing-library/jest-dom';

// Node 25 ships its own `localStorage` / `sessionStorage` globals, which are
// inert stubs unless node is started with `--localstorage-file`, and they shadow
// jsdom's working ones. Replace any stub with an in-memory Storage so code under
// test that persists to storage behaves as it does in a browser.
function memoryStorage() {
  const map = new Map();
  return {
    get length() { return map.size; },
    key: (i) => [...map.keys()][i] ?? null,
    getItem: (k) => (map.has(String(k)) ? map.get(String(k)) : null),
    setItem: (k, v) => { map.set(String(k), String(v)); },
    removeItem: (k) => { map.delete(String(k)); },
    clear: () => { map.clear(); },
  };
}

for (const name of ['localStorage', 'sessionStorage']) {
  const current = globalThis[name];
  if (!current || typeof current.setItem !== 'function') {
    Object.defineProperty(globalThis, name, { value: memoryStorage(), configurable: true, writable: true });
  }
}

/* global __dirname -- vitest defines it for setup files */
// RAIN data comes only from the backend (GET /api/v4/ui2/data). Tests hydrate the
// same data from a snapshot of that response (npm run fixtures:backend).
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { hydrateRainData } from '../data/rain/_shared/backendData';

hydrateRainData(
  JSON.parse(readFileSync(resolve(__dirname, 'fixtures/rain_v4_ui2_data.json'), 'utf8')),
  'src/test/fixtures/rain_v4_ui2_data.json',
);
