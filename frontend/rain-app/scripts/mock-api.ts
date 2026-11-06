/**
 * Mock Ultra API — `npm run mock-api` (port 5650, or MOCK_API_PORT).
 *
 * Serves the six v1 endpoints from the recorded adapter, i.e. from today's
 * scripted demos, so the backend team can see and test against the exact
 * payloads the UI consumes. Point the app at it with:
 *
 *   VITE_ULTRA_API_MODE=http VITE_ULTRA_API_BASE=http://localhost:5650 npm run dev
 *
 *   GET  /context?clientId=&personaId=
 *   GET  /briefing?clientId=&personaId=
 *   POST /ask            { clientId, personaId, input }
 *   POST /actions/:id    { clientId, personaId }
 *   GET  /catalog
 *   GET  /tts            (proxied by the real app; not served here)
 */
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRecordedApi, ApiError } from '../src/core/api/recorded';
import { getMarkets } from '../src/core/runtime/registry';

const api = createRecordedApi();
const PORT = Number(process.env.MOCK_API_PORT || 5650);
const CATALOG = join(dirname(fileURLToPath(import.meta.url)), '../docs/catalog/catalog.json');

function send(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  });
  res.end(JSON.stringify(body));
}

async function readJson(req: IncomingMessage): Promise<Record<string, string>> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {};
}

/**
 * Load every persona once, before listening and at top level. vite-node closes
 * its transform server when this entry module finishes evaluating, so every
 * module a request can need must be loaded by then; the HTTP server then
 * answers from the module cache. Retries cover a transform-server restart on
 * first import.
 */
async function warm() {
  const personas = getMarkets().flatMap((m) => m.clients.flatMap((c) => c.personas));
  for (const p of personas) {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try { await p.load(); break; } catch { await new Promise((r) => setTimeout(r, 300)); }
    }
  }
  return personas.length;
}

const server = createServer(async (req, res) => {
  if (req.method === 'OPTIONS') return send(res, 204, {});
  const url = new URL(req.url || '/', `http://localhost:${PORT}`);
  const q = Object.fromEntries(url.searchParams) as Record<string, string>;
  try {
    if (req.method === 'GET' && url.pathname === '/context') return send(res, 200, await api.getContext({ clientId: q.clientId, personaId: q.personaId }));
    if (req.method === 'GET' && url.pathname === '/briefing') return send(res, 200, await api.getBriefing({ clientId: q.clientId, personaId: q.personaId }));
    if (req.method === 'POST' && url.pathname === '/ask') {
      const b = await readJson(req);
      return send(res, 200, await api.ask({ clientId: b.clientId, personaId: b.personaId, input: b.input }));
    }
    const action = url.pathname.match(/^\/actions\/([^/]+)$/);
    if (req.method === 'POST' && action) {
      const b = await readJson(req);
      return send(res, 200, await api.runAction({ clientId: b.clientId, personaId: b.personaId, actionId: decodeURIComponent(action[1]) }));
    }
    if (req.method === 'GET' && url.pathname === '/catalog') return send(res, 200, JSON.parse(readFileSync(CATALOG, 'utf8')));
    return send(res, 404, { error: `No route ${req.method} ${url.pathname}` });
  } catch (err) {
    const status = err instanceof ApiError ? err.status : 500;
    return send(res, status, { error: err instanceof Error ? err.message : String(err) });
  }
});

const warmed = await warm();
server.listen(PORT, () => console.log(`Mock Ultra API on http://localhost:${PORT} (${warmed} personas)`));
