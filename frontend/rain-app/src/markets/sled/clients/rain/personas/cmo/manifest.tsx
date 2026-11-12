/**
 * Persona: Chief Medical Officer and Value-Based Care Quality Lead (Dr. Naomi Castellanos). Use Case A: the quality gate, the Winnemucca imaging cluster, what closes in 58 days, and the BP campaign handed to the Worklist.
 *
 * The whole persona comes from the backend (GET /api/v4/ui/data): its contract
 * (section "contracts": signals, kpis, steps, queries, viz, handoffs, workbenches)
 * and its identity, copy and notifications (section "personas"), built by the
 * shared RAIN builder.
 */
import { CONTRACTS } from '@/data/rain/contracts';
import { personaUi } from '@/data/rain/personaUi';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'cmo',
  ...personaUi('cmo'),
  contract: CONTRACTS.cmo,
  dataSources: ALL_SOURCES,
});

export default manifest;
