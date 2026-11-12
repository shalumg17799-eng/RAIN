/**
 * Persona: Community Health Worker and Care Coordinator (Teresa Lopez, CHW). Use Case B: a task briefing, then the Worklist (the BP campaign Dr. Castellanos sent) and Scheduling.
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
  key: 'chw',
  ...personaUi('chw'),
  contract: CONTRACTS.chw,
  dataSources: ALL_SOURCES,
});

export default manifest;
