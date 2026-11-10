/**
 * Persona: Chief Information Officer and Data and AI Governance Lead (Raj Malhotra). Use Case A (data trust): the impactability model fails its subgroup check on frontier ZIPs; the access-adjusted fix, the governance packet and sign-off.
 *
 * The whole persona comes from the backend (GET /api/v3/ui/data): its contract
 * (section "contracts": signals, kpis, steps, queries, viz, handoffs, workbenches)
 * and its identity, copy and notifications (section "personas"), built by the
 * shared RAIN builder.
 */
import { CONTRACTS } from '@/data/rain/contracts';
import { personaUi } from '@/data/rain/personaUi';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'cio',
  ...personaUi('cio'),
  contract: CONTRACTS.cio,
  dataSources: ALL_SOURCES,
});

export default manifest;
