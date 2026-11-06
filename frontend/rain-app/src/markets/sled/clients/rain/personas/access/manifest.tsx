/**
 * Persona: Patient Access Coordinator, the scheduler (Brandon Kee). Use Case B: a task briefing, then Scheduling (slots by drive time and mode, eligibility, booking, reminder plan) and Reminders.
 *
 * The whole persona is its contract, `data/rain/access.json` (signals, kpis,
 * steps, queries, viz, handoffs, workbenches), built by the shared RAIN builder.
 */
import contract from '@/data/rain/access.json';
import { CARE } from '@/data/rain/_shared/constants';
import type { RainContract } from '@/data/rain/_shared/contract';
import { ALL_SOURCES } from '@/data/rain/_shared/sources';
import { buildRainPersona } from '@/markets/sled/clients/rain/buildPersona';

const manifest = buildRainPersona({
  key: 'access',
  identity: { name: 'Brandon Kee', initials: 'BK', role: 'Patient Access Coordinator', greeting: 'Brandon' },
  contract: contract as unknown as RainContract,
  dataSources: ALL_SOURCES,
  inputPlaceholder: 'Ask about bookings, slots, unconfirmed visits or R replies…',
  greetingSubtitle: `Your morning briefing: ${CARE.brandonBookings} bookings, ${CARE.brandonUnconfirmed} unconfirmed visits and ${CARE.brandonRReplies} R replies.`,
  notifications: [
    { id: 'rk-n1', unread: true, title: '4 patients replied R', detail: "Each needs three new slots by SMS.", at: 'Today, 8:40 AM', tone: 'warning' },
  ],
});

export default manifest;
