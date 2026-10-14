// Browser-console trail of where every piece of on-screen data came from:
//   BACKEND   -- a response from the RAIN API (carries X-RAIN-Source: rain-api)
//   STATIC    -- bundled JSON/JSX, by design (no backend call exists)
//   FALLBACK  -- a backend call failed, so bundled data is shown instead
// Filter the console on "[RAIN data]" to see only these lines.

const TAG = '[RAIN data]';
const BADGE = {
  BACKEND: 'background:#16a34a;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  'BACKEND ERROR': 'background:#dc2626;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  STATIC: 'background:#6b7280;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
  FALLBACK: 'background:#d97706;color:#fff;padding:1px 6px;border-radius:3px;font-weight:bold',
};

function emit(kind, level, message, detail) {
  const args = [`%c${kind}%c ${TAG} ${message}`, BADGE[kind], ''];
  if (detail !== undefined) args.push(detail);
  console[level](...args);
}

/** A value on screen was produced by the backend. */
export function logBackend(what, detail) {
  emit('BACKEND', 'info', what, detail);
}

/** Bundled data shown by design -- this component never calls the backend. */
export function logStatic(what, file) {
  emit('STATIC', 'info', `${what} -- bundled data from ${file} (no backend call)`);
}

/** Bundled data shown because the backend call failed. */
export function logFallback(what, file, reason) {
  emit('FALLBACK', 'warn', `${what} -- backend unavailable (${reason}); showing bundled data from ${file}`);
}

function describeBody(body) {
  if (Array.isArray(body)) return `${body.length} items`;
  if (body && Array.isArray(body.visualization)) {
    return `visualization: ${body.visualization.map((v) => v.type).join(', ') || 'none'}`;
  }
  if (body && typeof body === 'object') return `keys: ${Object.keys(body).slice(0, 6).join(', ')}`;
  return typeof body;
}

/**
 * Wraps window.fetch once so every call to the RAIN API is logged with its
 * status, duration and the server's X-RAIN-Source header -- proof the data
 * came from the running backend, not the bundle. Other URLs pass through.
 */
export function installFetchLogger(apiBase) {
  if (window.__rainFetchLogger) return;
  window.__rainFetchLogger = true;
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    if (!url.startsWith(apiBase)) return realFetch(input, init);
    const method = (init && init.method) || 'GET';
    const path = url.slice(apiBase.length);
    const started = performance.now();
    try {
      const res = await realFetch(input, init);
      const ms = Math.round(performance.now() - started);
      const source = res.headers.get('X-RAIN-Source') || 'header missing';
      if (res.ok) {
        res.clone().json()
          .then((body) => logBackend(`${method} ${path} -> ${res.status} in ${ms} ms (X-RAIN-Source: ${source}) -- ${describeBody(body)}`, body))
          .catch(() => logBackend(`${method} ${path} -> ${res.status} in ${ms} ms (X-RAIN-Source: ${source})`));
      } else {
        emit('BACKEND ERROR', 'warn', `${method} ${path} -> HTTP ${res.status} in ${ms} ms`);
      }
      return res;
    } catch (err) {
      emit('BACKEND ERROR', 'error', `${method} ${path} -> network error after ${Math.round(performance.now() - started)} ms: ${err.message}. Is the API running at ${apiBase}?`);
      throw err;
    }
  };
  console.info(`${TAG} logging every request to ${apiBase}. Green BACKEND = live API data, amber FALLBACK = bundled data after a failed call, grey STATIC = bundled by design.`);
}
