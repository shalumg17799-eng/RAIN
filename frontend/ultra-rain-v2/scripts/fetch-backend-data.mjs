// Snapshot the LIVE RAIN backend's UI data (computed from rain_v4 rows) for checks against the backend.
//
//   npm run fixtures:backend                      (backend at http://localhost:8003, the rain4 stack)
//   RAIN_API=http://localhost:8000 npm run fixtures:backend
//
// The app itself never reads this file: in the browser every value comes from
// GET /api/v4/ui2/data at boot. The unit tests use the seed-built fixture
// (src/test/fixtures/rain_v4_ui2_data.json, scripts/e2e/make_ui2_test_fixture.py);
// this live snapshot (git-ignored) lets the Node scripts run on today's computed data:
//   RAIN_DATA_SNAPSHOT=src/test/fixtures/rain_v4_ui2_live.json npm run mock-api
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const base = (process.env.RAIN_API ?? 'http://localhost:8003').replace(/\/$/, '');
const url = `${base}/api/v4/ui2/data?clientId=rain`;
const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'test', 'fixtures', 'rain_v4_ui2_live.json');

const res = await fetch(url, { headers: { Accept: 'application/json' } });
if (!res.ok) {
  process.stderr.write(`GET ${url} answered ${res.status}\n`);
  process.exit(1);
}
const body = await res.json();
// Keep what the data is, not when it was served: a snapshot only changes when the data does.
const snapshot = {
  meta: {
    source: 'rain-api',
    snapshotOf: '/api/v4/ui2/data?clientId=rain',
    dataSource: body.meta?.dataSource,
    database: { ...body.meta?.database, configLoadedAt: undefined },
    asOf: body.meta?.computed?.asOf,
    periodEnd: body.meta?.computed?.periodEnd,
  },
  sections: body.sections,
};
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, `${JSON.stringify(snapshot, null, 1)}\n`);
const counts = Object.entries(body.sections).map(([k, v]) => `${k} ${Object.keys(v).length}`).join(', ');
process.stdout.write(`wrote ${out}\n  from ${url} (request ${res.headers.get('X-RAIN-Request-Id')})\n  ${counts}\n`);
