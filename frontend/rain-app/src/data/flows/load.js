/**
 * Load one persona's flow config on demand — for the callers that pick a
 * script by id at runtime (the screens' chat drawer, the platform-admin bar)
 * rather than through a persona manifest. Each config is its own chunk, so
 * these callers no longer pull every tenant's scripts into the app.
 *
 * Resolution matches the legacy lookup: a client-specific variant
 * (`<clientId>_<personaId>.js`, e.g. PenFed's own ops script) wins, then the
 * persona's own config, then the generic `ops` script.
 */
import { useEffect, useState } from 'react';

const LOADERS = import.meta.glob(['./*.js', '!./load.js', '!./shared.js'], { import: 'default' });
const loaderFor = (key) => LOADERS[`./${key}.js`];

export function flowConfigKey(clientId, personaId) {
  const id = personaId || 'ops';
  if (loaderFor(`${clientId}_${id}`)) return `${clientId}_${id}`;
  if (loaderFor(id)) return id;
  return clientId && loaderFor(`${clientId}_ops`) ? `${clientId}_ops` : 'ops';
}

export function loadFlowConfig(clientId, personaId) {
  return loaderFor(flowConfigKey(clientId, personaId))();
}

/** An empty script: nothing to say until the real one arrives. */
export const EMPTY_FLOW_CONFIG = Object.freeze({ chatFlows: {}, chipToFlowKey: {}, askTurnSequence: [], signalSequence: [] });

/** The persona's flow config, or null while it loads. */
export function usePersonaFlowConfig(clientId, personaId) {
  const key = flowConfigKey(clientId, personaId);
  const [loaded, setLoaded] = useState(null);
  useEffect(() => {
    let cancelled = false;
    loaderFor(key)().then((config) => { if (!cancelled) setLoaded({ key, config }); });
    return () => { cancelled = true; };
  }, [key]);
  return loaded?.key === key ? loaded.config : null;
}
