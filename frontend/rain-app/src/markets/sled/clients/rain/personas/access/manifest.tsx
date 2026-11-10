/**
 * Persona: Patient Access Coordinator, the scheduler (Brandon Kee). Use Case B: a task briefing, then Scheduling (slots by drive time and mode, eligibility, booking, reminder plan) and Reminders.
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
  key: 'access',
  ...personaUi('access'),
  contract: CONTRACTS.access,
  dataSources: ALL_SOURCES,
});

export default manifest;
