/**
 * Persona: Community Health Worker and Care Coordinator (Teresa Lopez, CHW). Use Case B: a task briefing, then the Worklist (the BP campaign Dr. Castellanos sent) and Scheduling.
 *
 * The whole persona is its contract, `data/rain/chw.json` (signals, kpis,
 * steps, queries, viz, handoffs, workbenches), built by the shared RAIN builder.
 */
import contract from '@/data/rain/chw.json';
import { CARE } from '@/data/rain/_shared/constants';
import type { RainContract } from '@/data/rain/_shared/contract';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'chw',
  identity: { name: 'Teresa Lopez, CHW', initials: 'TL', role: 'Community Health Worker and Care Coordinator', greeting: 'Teresa' },
  contract: contract as unknown as RainContract,
  dataSources: ALL_SOURCES,
  inputPlaceholder: 'Ask about your worklist, a patient, or who has not called back…',
  greetingSubtitle: `Your morning briefing: ${CARE.teresaTop} top-priority calls and ${CARE.teresaNoCallback} call-backs today.`,
  notifications: [
    { id: 'rt-n1', unread: true, title: 'BP campaign received', detail: "From Dr. Castellanos: 412 patients, 46 top priority at your sites.", at: 'Today, 7:05 AM', tone: 'info' },
  ],
});

export default manifest;
