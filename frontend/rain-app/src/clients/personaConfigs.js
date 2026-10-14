/**
 * Persona config assembler.
 * ─────────────────────────
 * Collects the RAIN persona UI + flow configs (co-located in
 * src/clients/rain/personaUI.js and personaFlows.js) into the flat,
 * persona-id-keyed maps the app consumes. src/data/personaUIConfig.js and
 * personaFlowConfigs.js re-export from here.
 *
 * ➜ To add a persona: edit src/clients/rain/personaUI.js + personaFlows.js
 *   (and the manifest's allowlist in src/clients/rain/index.js).
 */

import { rainUIConfigs } from '@/clients/rain/personaUI';
import { rainFlowConfigs } from '@/clients/rain/personaFlows';

// ─── UI configs (flat by persona id) ─────────────────────────────────────────
const personaUIConfigs = {
  ...rainUIConfigs,
};

// ─── Flow configs ────────────────────────────────────────────────────────────
const personaFlowConfigs = {
  ...rainFlowConfigs,
};

export function getPersonaFlowConfigs() {
  return personaFlowConfigs;
}

export { personaUIConfigs, personaFlowConfigs };
