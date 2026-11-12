/**
 * Persona: Program Lead, Rural Health Outcomes Accelerator (Dr. Lauren Pike; an illustrative role in the Nevada RHTP program). Use Case A at state scope: aggregated, de-identified county views, funding options and the CMS progress summary.
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
  key: 'state',
  ...personaUi('state'),
  contract: CONTRACTS.state,
  dataSources: ALL_SOURCES,
});

export default manifest;
