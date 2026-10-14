/**
 * Compatibility shim.
 * Per-persona UI configs now live with their clients (src/clients/<id>/personaUI.js)
 * and are assembled in src/clients/personaConfigs.js. Prefer importing
 * { personaUIConfigs } from '@/clients/personaConfigs' in new code.
 */
import { personaUIConfigs } from '@/clients/personaConfigs';

export default personaUIConfigs;
