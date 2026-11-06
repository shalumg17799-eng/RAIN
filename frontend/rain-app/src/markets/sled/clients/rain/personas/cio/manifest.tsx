/**
 * Persona: Chief Information Officer and Data and AI Governance Lead (Raj Malhotra). Use Case A (data trust): the impactability model fails its subgroup check on frontier ZIPs; the access-adjusted fix, the governance packet and sign-off.
 *
 * The whole persona is its contract, `data/rain/cio.json` (signals, kpis,
 * steps, queries, viz, handoffs, workbenches), built by the shared RAIN builder.
 */
import contract from '@/data/rain/cio.json';
import type { RainContract } from '@/data/rain/_shared/contract';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'cio',
  identity: { name: 'Raj Malhotra', initials: 'RM', role: 'Chief Information Officer and Data and AI Governance Lead', greeting: 'Raj' },
  contract: contract as unknown as RainContract,
  dataSources: ALL_SOURCES,
  inputPlaceholder: 'Ask about the risk model, data freshness, social needs coverage or patient matching…',
  greetingSubtitle: 'Your morning briefing: one item needs you before outreach starts.',
  notifications: [
    { id: 'ri-n1', unread: true, title: 'Subgroup check failed', detail: "Frontier ZIPs ranked 18% lower than similar members in town.", at: 'Today, 5:40 AM', tone: 'warning' },
    { id: 'ri-n2', unread: false, title: 'Claims feed landed', detail: "Q3 claims, 45 days after service.", at: 'Today, 4:00 AM', tone: 'info' },
  ],
});

export default manifest;
