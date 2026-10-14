/**
 * Compatibility shim.
 * Per-persona flow configs now live with their clients (src/clients/<id>/personaFlows.js)
 * and are assembled in src/clients/personaConfigs.js. Prefer importing from
 * '@/clients/personaConfigs' in new code.
 */
export { personaFlowConfigs as default, getPersonaFlowConfigs } from '@/clients/personaConfigs';
