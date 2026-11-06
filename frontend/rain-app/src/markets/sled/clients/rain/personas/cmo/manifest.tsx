/**
 * Persona: Chief Medical Officer and Value-Based Care Quality Lead (Dr. Naomi Castellanos). Use Case A: the quality gate, the Winnemucca imaging cluster, what closes in 58 days, and the BP campaign handed to the Worklist.
 *
 * The whole persona is its contract, `data/rain/cmo.json` (signals, kpis,
 * steps, queries, viz, handoffs, workbenches), built by the shared RAIN builder.
 */
import contract from '@/data/rain/cmo.json';
import type { RainContract } from '@/data/rain/_shared/contract';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'cmo',
  identity: { name: 'Dr. Naomi Castellanos', initials: 'NC', role: 'Chief Medical Officer and Value-Based Care Quality Lead', greeting: 'Dr. Castellanos' },
  contract: contract as unknown as RainContract,
  dataSources: ALL_SOURCES,
  inputPlaceholder: 'Ask about the quality gate, the BP campaign, low-value care or coding recapture…',
  greetingSubtitle: 'Your morning briefing: three quality signals need your call.',
  notifications: [
    { id: 'rm-n1', unread: true, title: 'Quality gate at 2 of 5', detail: "Blood pressure control is 7 points short.", at: 'Today, 6:15 AM', tone: 'warning' },
    { id: 'rm-n2', unread: false, title: 'Model co-sign may be requested', detail: "The CIO's governance packet lands in Model Governance.", at: 'Today, 6:20 AM', tone: 'info' },
  ],
});

export default manifest;
