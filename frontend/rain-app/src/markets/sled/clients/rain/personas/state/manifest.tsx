/**
 * Persona: Program Lead, Rural Health Outcomes Accelerator (Dr. Lauren Pike; an illustrative role in the Nevada RHTP program). Use Case A at state scope: aggregated, de-identified county views, funding options and the CMS progress summary.
 *
 * The whole persona is its contract, `data/rain/state.json` (signals, kpis,
 * steps, queries, viz, handoffs, workbenches), built by the shared RAIN builder.
 */
import contract from '@/data/rain/state.json';
import type { RainContract } from '@/data/rain/_shared/contract';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'state',
  identity: { name: 'Dr. Lauren Pike', initials: 'LP', role: 'Program Lead, Rural Health Outcomes Accelerator', greeting: 'Dr. Pike' },
  contract: contract as unknown as RainContract,
  dataSources: ALL_SOURCES,
  inputPlaceholder: 'Ask about county need, primary care access, low-value care, broadband or funding options…',
  greetingSubtitle: 'Your morning briefing: three signals across your four networks.',
  notifications: [
    { id: 'rs-n1', unread: true, title: 'Primary care visits down in two counties', detail: "Lander and Pershing, since the January 1 transition.", at: 'Today, 6:30 AM', tone: 'warning' },
  ],
});

export default manifest;
