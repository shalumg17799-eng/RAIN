/**
 * Persona: Patient (Linda Garcia, PRD v0.3 persona in v0.4, section 6.13). Use Case B, her own record only: the next visit
 * (day, time, mode, link), her reminder plan and how to reply C or R, sending a home blood pressure reading, missed
 * visits and how to reach the clinic. Her only workbench is her own text thread (the /patient view).
 *
 * The whole persona comes from the backend (GET /api/v4/ui/data): its contract
 * (section "contracts") and its identity, copy and notifications (section
 * "personas"), built by the shared RAIN builder.
 */
import { CONTRACTS } from '@/data/rain/contracts';
import { personaUi } from '@/data/rain/personaUi';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'linda',
  ...personaUi('linda'),
  contract: CONTRACTS.linda,
  dataSources: ALL_SOURCES,
});

export default manifest;
