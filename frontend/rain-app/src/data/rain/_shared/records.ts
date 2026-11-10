/**
 * Row-level records behind the workbenches: the 412-member blood pressure
 * campaign (which is also Teresa's worklist), Brandon's slots, bookings and
 * reminder log. Served by the backend (GET /api/v3/ui/data → section
 * "records"); these getters are the API seam and only type the rows.
 * Every person here is fictional.
 */
import type { CountyId } from './constants';
import { rainValue } from './backendData';

export type VisitMode = 'In person' | 'Telehealth';
export type CuffStatus = 'On file' | 'Ship first' | 'Not needed';
export type ContactStatus = 'Not contacted' | 'Left message' | 'Reached and booked' | 'Reached and declined' | 'Wrong number';

export interface CampaignMember {
  id: string;
  rank: number;
  name: string;
  age: number;
  siteId: string;
  site: string;
  county: CountyId;
  driveMin: number;
  /** Last office or home reading. */
  lastBp: string;
  lastBpMonth: string;
  monthsSinceVisit: number;
  /** Likelihood of reaching control with a recheck, 0 to 100. */
  likelihood: number;
  mode: VisitMode;
  cuff: CuffStatus;
  reasons: string[];
  language: 'English' | 'Spanish';
  channel: 'SMS' | 'Voice';
  socialNeeds: string[];
  conditions: string[];
  /** Fictional number in the 555-01xx range reserved for fiction. */
  phone: string;
  bestTime: string;
  /** Anything the caller should know before dialling (a shared phone). */
  phoneNote?: string;
  lastContact: string;
  status: ContactStatus;
  standingOrder: string;
  /** In Teresa's 46 top-priority patients this week. */
  teresaTop: boolean;
  frontier: boolean;
}

/** GET /campaigns/bp412/members (backend: records.campaignMembers). */
export function getCampaignMembers(): CampaignMember[] {
  return rainValue<CampaignMember[]>('records', 'campaignMembers');
}

/** Teresa's 46 top-priority patients this week. */
export const getTeresaWorklist = () => getCampaignMembers().filter((m) => m.teresaTop);

export const getMember = (id: string) => getCampaignMembers().find((m) => m.id === id);

// ─── Scheduling (Brandon) ───────────────────────────────────────────────────

export interface Slot {
  id: string;
  mode: 'Telehealth (video)' | 'Mobile clinic' | 'In person';
  where: string;
  provider: string;
  day: string;
  time: string;
  driveMin: number;
}

/** GET /slots?member=… (backend: records.slots). */
export function getSlots(): Slot[] {
  return rainValue<Slot[]>('records', 'slots');
}

export interface Booking {
  memberId: string;
  name: string;
  from: string;
  mode: VisitMode;
  eligibility: 'Active' | 'Lapsed';
  planName: string;
}

/** GET /bookings/pending (backend: records.pendingBookings). */
export function getPendingBookings(): Booking[] {
  return rainValue<Booking[]>('records', 'pendingBookings');
}

// ─── Reminders (Brandon) ────────────────────────────────────────────────────

export interface ReminderRow {
  memberId: string;
  name: string;
  visit: string;
  language: 'English' | 'Spanish';
  plan: string;
  status: 'Confirmed (C)' | 'Change requested (R)' | 'No reply yet' | 'Scheduled';
  log: Array<{ at: string; dir: 'out' | 'in'; text: string }>;
}

/** GET /reminders (backend: records.reminders). */
export function getReminders(): ReminderRow[] {
  return rainValue<ReminderRow[]>('records', 'reminders');
}

// The CIO's governance records live in their own file; re-exported so importers stay unchanged.
export { FEATURES, SUBGROUP, getAccessPoints, getSwaps } from './governance';
export type { ModelFeature, SwapRow } from './governance';
