/**
 * Row-level synthetic records behind the workbenches: the 412-member blood
 * pressure campaign (which is also Teresa's worklist), Brandon's slots and
 * reminder log, the subgroup-check members and the drive-time scatter.
 *
 * Generated from a fixed seed, so the demo shows the same rows every time and
 * `rain.test.ts` can check each set against the master numbers. These getters
 * are the API seam: a backend replaces each one with an endpoint and no
 * component changes. Every person here is fictional.
 */
import { BP, CARE, LINDA, SITES } from './constants';
import type { CountyId } from './constants';
import { seeded } from './seeded';

const FIRST = ['Maria', 'James', 'Rosa', 'Daniel', 'Elena', 'Robert', 'Carmen', 'Michael', 'Ana', 'David', 'Lucia', 'Thomas', 'Patricia', 'Jose', 'Sandra', 'William', 'Gloria', 'Richard', 'Teresa', 'Joseph', 'Martha', 'Charles', 'Irene', 'Luis', 'Nancy', 'Frank', 'Diane', 'Miguel', 'Karen', 'Paul', 'Alicia', 'Mark', 'Beatriz', 'Steven', 'Joyce', 'Carlos', 'Helen', 'Raymond', 'Silvia', 'Gary'];
const LAST = ['Martinez', 'Johnson', 'Hernandez', 'Smith', 'Lopez', 'Brown', 'Gonzalez', 'Davis', 'Perez', 'Miller', 'Sanchez', 'Wilson', 'Ramirez', 'Moore', 'Torres', 'Taylor', 'Flores', 'Anderson', 'Rivera', 'Thomas', 'Gomez', 'Jackson', 'Diaz', 'White', 'Reyes', 'Harris', 'Cruz', 'Martin', 'Morales', 'Thompson', 'Ortiz', 'Clark', 'Gutierrez', 'Lewis', 'Chavez', 'Walker', 'Ramos', 'Hall', 'Castillo', 'Young'];

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

const MONTHS = ['May', 'June', 'July', 'August', 'September'];

/** The 412 near-control members, ranked by likelihood of reaching control. */
function buildCampaign(): CampaignMember[] {
  const rnd = seeded(20260412);
  const pick = <T,>(xs: readonly T[]) => xs[Math.floor(rnd() * xs.length)];
  // Site shares of the 412 (illustrative), summing to 412.
  const perSite: Record<string, number> = { elko: 88, wells: 30, winnemucca: 92, battleMountain: 58, lovelock: 40, ely: 46, fallon: 58 };
  const rows: Omit<CampaignMember, 'rank' | 'teresaTop' | 'mode' | 'cuff' | 'phone' | 'bestTime' | 'phoneNote'>[] = [];
  let n = 0;
  for (const site of SITES) {
    for (let i = 0; i < perSite[site.id]; i += 1) {
      n += 1;
      const far = rnd() < 0.66;
      const driveMin = far ? 61 + Math.floor(rnd() * 70) : 8 + Math.floor(rnd() * 50);
      const sys = 141 + Math.floor(rnd() * 9);
      const dia = 84 + Math.floor(rnd() * 9);
      const months = 2 + Math.floor(rnd() * 9);
      const spanish = rnd() < 0.34;
      const social = [rnd() < 0.3 ? 'Transportation' : '', rnd() < 0.12 ? 'Food' : '', rnd() < 0.08 ? 'Housing' : ''].filter(Boolean);
      const reasons = [
        `BP ${sys}/${dia} in ${pick(MONTHS)}`,
        driveMin > 60 ? `${driveMin}-minute drive` : `${driveMin}-minute drive to ${site.name}`,
        months >= 6 ? `No visit in ${months} months` : rnd() < 0.5 ? 'Avoidable ED visit this year' : 'Open diabetes gap',
      ];
      rows.push({
        id: `M-${(40100 + n * 7).toString()}`,
        name: `${pick(FIRST)} ${pick(LAST)}`,
        age: 34 + Math.floor(rnd() * 40),
        siteId: site.id,
        site: site.name,
        county: site.county,
        driveMin,
        lastBp: `${sys}/${dia}`,
        lastBpMonth: reasons[0].split(' in ')[1],
        reasons,
        monthsSinceVisit: months,
        likelihood: 40 + Math.floor(rnd() * 48),
        language: spanish ? 'Spanish' : 'English',
        channel: rnd() < 0.85 ? 'SMS' : 'Voice',
        socialNeeds: social,
        conditions: rnd() < 0.42 ? ['Hypertension', 'Type 2 diabetes'] : ['Hypertension'],
        lastContact: 'None this campaign',
        status: 'Not contacted',
        standingOrder: 'BP recheck; titrate per protocol if 140/90 or higher',
        frontier: driveMin > 60 && rnd() < 0.5,
      });
    }
  }
  // Linda leads the campaign (plan D13).
  rows[0] = {
    ...rows[0],
    id: 'M-40107',
    name: LINDA.name,
    age: LINDA.age,
    siteId: 'battleMountain',
    site: 'Battle Mountain',
    county: 'lander',
    driveMin: LINDA.driveMin,
    lastBp: LINDA.bp,
    lastBpMonth: LINDA.bpMonth,
    monthsSinceVisit: LINDA.monthsSinceVisit,
    likelihood: 94,
    language: 'Spanish',
    channel: 'SMS',
    socialNeeds: ['Transportation'],
    conditions: ['Hypertension', 'Type 2 diabetes'],
    lastContact: 'Missed 2 visits',
    frontier: true,
    standingOrder: 'BP recheck by video with home cuff; titrate per protocol',
  };
  rows[0].reasons = [`BP ${LINDA.bp} in ${LINDA.bpMonth}`, `${LINDA.driveMin}-minute drive`, `No visit in ${LINDA.monthsSinceVisit} months`];
  // Exactly 268 drive more than an hour (telehealth); the rest are in person.
  const byDrive = [...rows].sort((a, b) => (a.id === 'M-40107' ? -1 : b.id === 'M-40107' ? 1 : b.driveMin - a.driveMin));
  byDrive.forEach((r, i) => {
    if (i < BP.telehealth && r.driveMin <= 60) r.driveMin = 61 + (i % 50);
    if (i >= BP.telehealth && r.driveMin > 60) r.driveMin = 20 + (i % 40);
  });
  // Reasons and the frontier flag follow the final drive time.
  rows.forEach((r, i) => {
    if (r.id === 'M-40107') return;
    const site = SITES.find((s) => s.id === r.siteId)!;
    r.reasons = [
      `BP ${r.lastBp} in ${r.lastBpMonth}`,
      r.driveMin > 60 ? `${r.driveMin}-minute drive` : `${r.driveMin}-minute drive to ${site.name}`,
      r.monthsSinceVisit >= 6 ? `No visit in ${r.monthsSinceVisit} months` : i % 2 || !r.conditions.includes('Type 2 diabetes') ? 'Avoidable ED visit this year' : 'Open diabetes gap',
    ];
    r.frontier = r.driveMin > 60 && i % 2 === 0;
  });
  const ranked = [...rows].sort((a, b) => (a.id === 'M-40107' ? -1 : b.id === 'M-40107' ? 1 : b.likelihood - a.likelihood));
  let shipped = 0;
  let teresa = 0;
  return ranked.map((r, i) => {
    const mode: VisitMode = r.driveMin > 60 ? 'Telehealth' : 'In person';
    let cuff: CuffStatus = 'Not needed';
    if (mode === 'Telehealth') {
      cuff = i > 0 && shipped < BP.cuffsToShip && i % 7 === 3 ? 'Ship first' : 'On file';
      if (cuff === 'Ship first') shipped += 1;
    }
    const mine = r.siteId === 'winnemucca' || r.siteId === 'battleMountain';
    const top = mine && teresa < CARE.teresaTop;
    if (top) teresa += 1;
    const isLinda = r.id === 'M-40107';
    // Derived from the id, not the generator, so adding contact fields leaves every other value unchanged.
    const n = Number(r.id.slice(2));
    // Teresa's 46 get distinct numbers (0110 to 0155); the rest reuse the fictional range.
    const line = top ? 109 + teresa : n % 100;
    const contact = isLinda
      ? { phone: '(775) 555-0107', bestTime: 'After 5 PM', phoneNote: 'Shared family phone; ask for Linda' }
      : { phone: `(775) 555-01${String(line % 100).padStart(2, '0')}`, bestTime: BEST_TIMES[n % BEST_TIMES.length] };
    return { ...r, ...contact, rank: i + 1, mode, cuff, teresaTop: top };
  });
}

const BEST_TIMES = ['Mornings', 'After 5 PM', 'Midday', 'Any time'];

/**
 * The patients Teresa called yesterday who have not called back (her
 * greeting's five): left a message, and each has a call task today. They sit
 * just below the top of her list, so the first patients she opens are new calls.
 */
function markNoCallback(rows: CampaignMember[]) {
  rows
    .filter((m) => m.teresaTop && m.rank > 1)
    .slice(6, 6 + CARE.teresaNoCallback)
    .forEach((m) => {
      m.status = 'Left message';
      m.lastContact = 'Yesterday, left message';
    });
}

/** One person per name: a repeat takes the next free surname. */
function dedupeNames(rows: CampaignMember[]) {
  const seen = new Set<string>();
  rows.forEach((m) => {
    const [given, surname] = m.name.split(' ');
    // No patient shares a first name with the care team's Teresa.
    const first = given === 'Teresa' ? 'Irma' : given;
    let last = surname;
    let k = LAST.indexOf(last);
    while (seen.has(`${first} ${last}`)) {
      k = (k + 1) % LAST.length;
      last = LAST[k];
    }
    m.name = `${first} ${last}`;
    seen.add(m.name);
  });
}

let campaignCache: CampaignMember[] | null = null;

/** GET /campaigns/bp412/members */
export function getCampaignMembers(): CampaignMember[] {
  if (!campaignCache) {
    const rows = buildCampaign();
    // Top up cuff shipments to exactly 37 if the stride fell short.
    let shipped = rows.filter((r) => r.cuff === 'Ship first').length;
    for (const r of rows) {
      if (shipped >= BP.cuffsToShip) break;
      if (r.mode === 'Telehealth' && r.cuff === 'On file' && r.rank > 1) {
        r.cuff = 'Ship first';
        shipped += 1;
      }
    }
    dedupeNames(rows);
    markNoCallback(rows);
    markBooked(rows);
    campaignCache = rows;
  }
  return campaignCache;
}

/** GET /worklists/teresa (her 46 top-priority patients this week). */
export const getTeresaWorklist = () => getCampaignMembers().filter((m) => m.teresaTop);

export const getMember = (id: string) => getCampaignMembers().find((m) => m.id === id);

/**
 * The campaign's bookings so far (62 of 412), none from Teresa's 46 this week.
 * Thirteen are at her two sites: tomorrow's 9 unconfirmed visits and the 4 R
 * replies in Brandon's Reminders; the other 49 are at the other five sites.
 */
const atTeresaSites = (m: CampaignMember) => m.siteId === 'winnemucca' || m.siteId === 'battleMountain';
function markBooked(rows: CampaignMember[]) {
  const pool = rows.filter((m) => m.rank > 1 && !m.teresaTop);
  const local = pool.filter(atTeresaSites).slice(0, CARE.brandonUnconfirmed + CARE.brandonRReplies);
  const other = pool.filter((m) => !atTeresaSites(m)).slice(0, CARE.booked - local.length);
  [...local, ...other].forEach((m) => {
    m.status = 'Reached and booked';
    m.lastContact = 'Visit booked';
  });
}

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

/** GET /slots?member=… (for Linda: open slots across sites and telehealth). */
export function getSlots(): Slot[] {
  return [
    { id: 'S1', mode: 'Telehealth (video)', where: 'Video visit', provider: 'Dr. Ana Ruiz', day: 'Thu, Nov 5', time: '2:00 PM', driveMin: 0 },
    { id: 'S2', mode: 'Telehealth (video)', where: 'Video visit', provider: 'Jordan Pace, NP', day: 'Thu, Nov 5', time: '4:30 PM', driveMin: 0 },
    { id: 'S3', mode: 'Telehealth (video)', where: 'Video visit', provider: 'Dr. Ana Ruiz', day: 'Fri, Nov 6', time: '9:00 AM', driveMin: 0 },
    { id: 'S4', mode: 'Mobile clinic', where: 'Mobile clinic, Battle Mountain', provider: 'Mobile team', day: 'Tue, Nov 10', time: '10:00 AM', driveMin: 14 },
    { id: 'S5', mode: 'In person', where: 'Sierra Basin Winnemucca', provider: 'Dr. Owen Hale', day: 'Mon, Nov 9', time: '1:15 PM', driveMin: LINDA.driveMin },
    { id: 'S6', mode: 'In person', where: 'Sierra Basin Winnemucca', provider: 'Dr. Owen Hale', day: 'Wed, Nov 11', time: '8:30 AM', driveMin: LINDA.driveMin },
  ];
}

export interface Booking {
  memberId: string;
  name: string;
  from: string;
  mode: VisitMode;
  eligibility: 'Active' | 'Lapsed';
  planName: string;
}

/**
 * GET /bookings/pending: the 23 waiting from Teresa's worklist (Linda first,
 * one lapsed). Patients still to call back are not among them.
 */
export function getPendingBookings(): Booking[] {
  const members = getTeresaWorklist().filter((m) => m.status !== 'Left message');
  return members.slice(0, CARE.brandonBookings).map((m, i) => ({
    memberId: m.id,
    name: m.name,
    from: 'Teresa Lopez, CHW',
    mode: m.mode,
    eligibility: i === 4 ? 'Lapsed' : 'Active',
    planName: 'High Desert Health Plan',
  }));
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

/**
 * GET /reminders: tomorrow's 9 unconfirmed, the 4 R replies, and Linda's plan.
 * The others are booked patients at Teresa's two sites from outside her 46, so
 * a missed reply can become a call task on her worklist.
 */
export function getReminders(): ReminderRow[] {
  const members = getCampaignMembers().filter((m) => !m.teresaTop && m.status === 'Reached and booked' && atTeresaSites(m));
  const rows: ReminderRow[] = [
    {
      memberId: 'M-40107',
      name: LINDA.name,
      visit: `${LINDA.visit.day}, ${LINDA.visit.date}, ${LINDA.visit.time} · video`,
      language: 'Spanish',
      plan: '72 h, 24 h and 3 h before · quiet hours 8 PM to 8 AM',
      status: 'Scheduled',
      log: [],
    },
  ];
  members.slice(0, CARE.brandonUnconfirmed).forEach((m, i) => {
    rows.push({
      memberId: m.id,
      name: m.name,
      visit: `Tomorrow, ${clock(9 + i, i % 2 ? '30' : '00')} · ${m.mode === 'Telehealth' ? 'video' : m.site}`,
      language: m.language,
      plan: '24 h and 3 h before',
      status: 'No reply yet',
      log: [{ at: 'Today, 8:00 AM', dir: 'out', text: 'Reminder sent: reply C to confirm or R to change.' }],
    });
  });
  members.slice(CARE.brandonUnconfirmed, CARE.brandonUnconfirmed + CARE.brandonRReplies).forEach((m, i) => {
    rows.push({
      memberId: m.id,
      name: m.name,
      visit: `${['Mon', 'Tue', 'Wed', 'Thu'][i % 4]}, Nov ${9 + i}, 10:00 AM · ${m.mode === 'Telehealth' ? 'video' : m.site}`,
      language: m.language,
      plan: '72 h, 24 h and 3 h before',
      status: 'Change requested (R)',
      log: [
        { at: 'Today, 8:15 AM', dir: 'out', text: 'Visit booked: reply C to confirm or R to change.' },
        { at: 'Today, 8:40 AM', dir: 'in', text: 'R' },
      ],
    });
  });
  return rows;
}

/** "13:30" as "1:30 PM". */
function clock(hour: number, min: string) {
  return `${hour > 12 ? hour - 12 : hour}:${min} ${hour >= 12 ? 'PM' : 'AM'}`;
}

// The CIO's governance records live in their own file; re-exported so importers stay unchanged.
export { FEATURES, SUBGROUP, getAccessPoints, getSwaps } from './governance';
export type { ModelFeature, SwapRow } from './governance';
