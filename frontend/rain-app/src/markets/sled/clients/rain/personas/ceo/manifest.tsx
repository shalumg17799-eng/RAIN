/**
 * Persona: Chief Executive Officer (Gregory Haskins, MBA), default persona. Use Case A: the Q3 contract checkpoint seen as money: the $26 gap, what is recoverable by December 31, and the board brief with two hand-offs.
 *
 * The whole persona is its contract, `data/rain/ceo.json` (signals, kpis,
 * steps, queries, viz, handoffs, workbenches), built by the shared RAIN builder.
 */
import contract from '@/data/rain/ceo.json';
import type { RainContract } from '@/data/rain/_shared/contract';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'ceo',
  identity: { name: 'Gregory Haskins, MBA', initials: 'GH', role: 'Chief Executive Officer', greeting: 'Gregory' },
  contract: contract as unknown as RainContract,
  dataSources: ALL_SOURCES,
  inputPlaceholder: 'Ask about cost against expected, the quality gate, low-value care or your sites…',
  greetingSubtitle: 'Your morning briefing: three signals from the Q3 checkpoint.',
  notifications: [
    { id: 'rc-n1', unread: false, title: 'Q3 reconciliation received', detail: "High Desert Health Plan, 9,400 attributed members.", at: 'Today, 6:10 AM', tone: 'info' },
    { id: 'rc-n2', unread: true, title: 'Board meets this month', detail: "The board brief is one click away in Ask AI.", at: 'Today, 7:00 AM', tone: 'warning' },
  ],
});

export default manifest;
