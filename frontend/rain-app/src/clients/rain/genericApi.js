// Every card asks for its data by Component name (optionally a Variant)
// through the one shared /api/v2/generic endpoint -- no card gets its own
// bespoke route. This is what lets a new card, a new persona, or a new
// domain reuse the same 4 generic APIs (signals / kpis / ask / generic)
// instead of growing a new endpoint each time.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

import { logBackend, logFallback } from '../../utils/dataLog';

async function requestComponent(component, persona, variant) {
  const res = await fetch(`${API_BASE}/api/v2/generic`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      market: 'healthcare', product: 'rain', persona,
      category: [{ component, ...(variant ? { variant } : {}) }],
    }),
  });
  if (!res.ok) throw new Error('unavailable');
  const body = await res.json();
  const entry = body.visualization && body.visualization.find((v) => v.type === component);
  if (!entry || !entry.data || entry.data.error) throw new Error(entry && entry.data ? entry.data.error : 'no resolver');
  return entry.data;
}

// Every caller renders its bundled STATIC_* card when this throws, so the
// fallback is logged here once for all of them.
export async function fetchGenericComponent(component, persona, variant) {
  try {
    const data = await requestComponent(component, persona, variant);
    logBackend(`${component} card rendered from POST /api/v2/generic (persona ${persona})`);
    return data;
  } catch (err) {
    logFallback(`${component} card`, 'the card\'s own STATIC_* constants', err.message);
    throw err;
  }
}
