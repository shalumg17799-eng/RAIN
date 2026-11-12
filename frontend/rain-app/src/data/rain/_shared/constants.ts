/**
 * RAIN master numbers: the Q3 value-based contract checkpoint at Sierra Basin
 * Community Health (a fictional FQHC network). Every value here comes from the
 * backend (GET /api/v4/ui/data → Postgres rain_v4.ui_v4.dataset, section
 * "constants"); this module only types them and keeps the formatting helpers.
 * The county public fields (htnPct, diabetesPct, svi, hpsa) are computed live
 * by the backend from rain_v4.public_data (CDC PLACES, CDC/ATSDR SVI, HRSA).
 */
import { rainValue } from './backendData';

const C = <T,>(key: string) => rainValue<T>('constants', key);

export type PersonaKey = 'ceo' | 'cmo' | 'cio' | 'state' | 'chw' | 'access' | 'linda';
export type MeasureId = 'CMS2' | 'CMS125' | 'CMS165' | 'CMS122' | 'CMS130';
export type CountyId = 'elko' | 'humboldt' | 'lander' | 'pershing' | 'whitePine' | 'churchill';

export const ILLUSTRATIVE = C<string>('ILLUSTRATIVE');

/** Persona key → id, in switcher order. */
export const PERSONAS = C<Readonly<Record<PersonaKey, string>>>('PERSONAS');

export const ORG = C<{ readonly network: string; readonly networkShort: string; readonly plan: string; readonly program: string; readonly product: string }>('ORG');

// ─── Formatting ─────────────────────────────────────────────────────────────

export const num = (n: number) => n.toLocaleString('en-US');
export const usd = (n: number, digits = 0) => `$${n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
export const usdK = (n: number) => `$${Math.round(n / 1000).toLocaleString('en-US')}K`;
export const usdM = (n: number, digits = 1) => `$${(n / 1_000_000).toFixed(digits)}M`;

// ─── The contract ───────────────────────────────────────────────────────────

export const CONTRACT = C<{
  readonly members: number; readonly actualPmpm: number; readonly expectedPmpm: number; readonly abovePct: number;
  readonly annualGap: number; readonly daysLeft: number; readonly gateNeeded: number; readonly gateMeasures: number;
  readonly gateMet: number; readonly claimsLagDays: number;
}>('CONTRACT');

/** The $26 PMPM gap in four parts. */
export const GAP = C<ReadonlyArray<{ readonly id: 'coding' | 'ed' | 'lowValue' | 'other'; readonly label: string; readonly value: number; readonly note: string }>>('GAP');
export const GAP_TOTAL = GAP.reduce((s, g) => s + g.value, 0);

/** Segmentation by impactability. */
export const SEGMENTS = C<ReadonlyArray<{ readonly id: 'highNeed' | 'impactable' | 'stable'; readonly label: string; readonly members: number; readonly sharePct: number; readonly spendPct: number; readonly action: string }>>('SEGMENTS');

export const COHORT = C<{ readonly topRanked: number; readonly avoidedCost12m: number }>('COHORT');

export const CODING = C<{ readonly members: number; readonly ofHighNeed: number; readonly sharePct: number; readonly understatedPct: number; readonly correctedBenchmark: number; readonly gapAfterPct: number }>('CODING');

export const LOW_VALUE = C<{
  readonly services: number; readonly annual: number; readonly measures: number; readonly lbpImaging: number;
  readonly winnemuccaSharePct: number; readonly networkRatePct: number; readonly winnemuccaRatePct: number;
  readonly rotationMonth: string; readonly clinicians: number;
}>('LOW_VALUE');

export const ED = C<{ readonly per1000: number; readonly benchmark: number }>('ED');

/** The five gate measures. `higherIsBetter: false` for HbA1c poor control. */
export const MEASURES = C<ReadonlyArray<{ readonly id: MeasureId; readonly name: string; readonly current: number; readonly target: number; readonly higherIsBetter: boolean; readonly projected: number }>>('MEASURES');
export const isMet = (m: { current: number; target: number; higherIsBetter: boolean }) => (m.higherIsBetter ? m.current >= m.target : m.current <= m.target);

/** The blood pressure campaign. */
export const BP = C<{
  readonly hypertensive: number; readonly nearControl: number; readonly withinPoints: number; readonly needed: number;
  readonly projected: number; readonly inPerson: number; readonly telehealth: number; readonly cuffsToShip: number; readonly shortPts: number;
}>('BP');

export const FIT = C<{ readonly gainPts: number }>('FIT');

// ─── CIO ────────────────────────────────────────────────────────────────────

export const MODEL = C<{
  readonly name: string; readonly version: string; readonly candidate: string; readonly frontierGapPct: number;
  readonly frontierGapAfterPct: number; readonly releaseThresholdPct: number; readonly missingFromTop: number;
  readonly inBpDenominator: number; readonly fewerVisitsPct: number; readonly medianDriveMin: number;
  readonly noBroadband: number; readonly socialScreenedPct: number; readonly publicSources: number;
  readonly syntheticSources: number; readonly adtLag: string; readonly auc: number; readonly unmatchedRecords: number;
}>('MODEL');

// ─── State ──────────────────────────────────────────────────────────────────

export const STATE = C<{
  readonly networks: number; readonly sites: number; readonly members: number; readonly counties: number;
  readonly hpsaCounties: number; readonly edPer1000: number; readonly lowValue: number; readonly pcVisitDropPct: number;
  readonly lowBroadbandZips: number; readonly broadbandFloorPct: number; readonly suppressUnder: number; readonly optionAEdCutPct: number;
}>('STATE');

// ─── Care team ──────────────────────────────────────────────────────────────

export const CARE = C<{
  readonly teresaTop: number; readonly teresaNoCallback: number; readonly teresaOpen: number; readonly booked: number;
  readonly controlled: number; readonly brandonBookings: number; readonly brandonUnconfirmed: number;
  readonly brandonRReplies: number; readonly telehealthProviders: number;
}>('CARE');

export const LINDA = C<{
  readonly name: string; readonly first: string; readonly age: number; readonly town: string; readonly driveMin: number;
  readonly bp: string; readonly bpMonth: string; readonly monthsSinceVisit: number; readonly missedVisits: number;
  readonly language: string; readonly reading: string; readonly link: string; readonly memberId: string;
  readonly visit: { readonly day: string; readonly date: string; readonly time: string; readonly es: string };
}>('LINDA');

// ─── Sites and counties ─────────────────────────────────────────────────────

export interface Site {
  id: string;
  name: string;
  county: CountyId;
  members: number;
  pmpm: number;
  /** Low back pain imaging as a share of eligible visits. */
  imagingPct: number;
  lowValue: number;
  locum: boolean;
}

export const SITES = C<Site[]>('SITES');
export const siteById = (id: string) => SITES.find((s) => s.id === id);

/** Teresa's two sites (her worklist and Brandon's reminders). */
export const TERESA_SITES = C<ReadonlyArray<string>>('TERESA_SITES');

/** Members with a social needs screening, by site (%). */
export const SITE_SOCIAL = C<Readonly<Record<string, number>>>('SITE_SOCIAL');

/** PMPM by month since January. */
export const PMPM_TREND = C<ReadonlyArray<{ readonly month: string; readonly actual: number }>>('PMPM_TREND');

/** Winnemucca low back pain imaging rate by month. */
export const WINNEMUCCA_TREND = C<ReadonlyArray<{ readonly month: string; readonly value: number }>>('WINNEMUCCA_TREND');

/** The three rotating clinicians at Winnemucca, de-identified. */
export const LOCUMS = C<ReadonlyArray<{ readonly id: string; readonly ratePct: number; readonly orders: number }>>('LOCUMS');

/** The 14-measure low-value care library. */
export const LV_MEASURES = C<ReadonlyArray<{ readonly id: string; readonly name: string; readonly basis: string; readonly services: number; readonly dollars: number }>>('LV_MEASURES');

/** Six-county state view. htnPct, diabetesPct, svi and hpsa are live public data from the backend. */
export interface County {
  id: CountyId;
  name: string;
  members: number;
  htnPct: number;
  diabetesPct: number;
  svi: number;
  hpsa: 'Whole county' | 'Part of county';
  broadbandPct: number;
  pcVisitChangePct: number;
  edPer1000: number;
  lowValue: number;
  /** Members with heart failure in view; under 11 is suppressed. */
  heartFailure: number;
  bpControlPct: number;
  /** Where each public field came from, as reported by the backend. */
  publicSources?: Partial<Record<'htnPct' | 'diabetesPct' | 'svi' | 'hpsa', string>>;
}

export const COUNTIES = C<County[]>('COUNTIES');
export const countyById = (id: string) => COUNTIES.find((c) => c.id === id);

/** A count under the state's privacy floor is shown as a dash. */
export const suppress = (n: number) => (n < STATE.suppressUnder ? '–' : num(n));

/** The four participating networks. */
export const NETWORKS = C<ReadonlyArray<{ readonly id: string; readonly name: string; readonly sites: number; readonly bpControlPct: number; readonly colorectalPct: number; readonly edPer1000: number }>>('NETWORKS');

/** The three funding options. */
export const OPTIONS = C<ReadonlyArray<{ readonly id: string; readonly name: string; readonly reach: number; readonly cost: number; readonly outcome: string; readonly time: string; readonly impact: string }>>('OPTIONS');

/** The six low-broadband ZIP areas (named by town). */
export const LOW_BB_PLACES = C<ReadonlyArray<string>>('LOW_BB_PLACES');

/** Data freshness, shown on every Use Case A view. */
export const FRESHNESS = C<string>('FRESHNESS');

// ─── the patient persona: data scope, task briefing and own record ──

/** A scoped persona's data scope: the patient sees her own record only. */
export const SCOPES = C<Readonly<Record<string, { readonly label: string; readonly self?: boolean; readonly memberId?: string }>>>('SCOPES');

/** Task briefings served by the backend (the patient's, built from her own record). */
export interface TaskQueue {
  readonly title: string;
  readonly items: ReadonlyArray<{ readonly n: number; readonly label: string; readonly tone: 'warning' | 'critical' | 'neutral' }>;
  readonly first: string;
  readonly button: { readonly label: string; readonly href: string };
}
export const TASKS = C<Readonly<Record<string, TaskQueue>>>('TASKS');

/**
 * The patient persona's own record, computed by the backend from her rows only
 * (rain-api/metrics_personas_v4.py). A patient persona reads nothing else.
 */
export interface PatientRecord {
  readonly memberId: string; readonly name: string; readonly first: string; readonly age: number; readonly language: string;
  readonly town: string; readonly site: string; readonly siteAddress: string; readonly county: string; readonly driveMin: number; readonly plan: string;
  readonly next: { readonly appointmentId: string; readonly when: string; readonly day: string; readonly date: string; readonly time: string; readonly es: string; readonly mode: string; readonly modeA: string; readonly where: string; readonly provider: string; readonly visitType: string; readonly link: string; readonly daysAway: number; readonly status: string };
  readonly upcoming: number; readonly unconfirmed: number; readonly status: string; readonly noShowBand: string; readonly noShowRiskPct: number;
  readonly reminders: { readonly planned: number; readonly sent: number; readonly toCome: number; readonly replies: number; readonly noReply: number; readonly offsets: string; readonly channel: string; readonly language: string; readonly offersVideo: boolean; readonly videoOffer: string };
  readonly contact: { readonly channels: string; readonly channelCount: number; readonly bestTime: string; readonly quietHours: string; readonly phoneNote: string; readonly frontDesk: string; readonly clinical: string; readonly messages: number; readonly openMessages: number };
  readonly readings: { readonly count: number; readonly latest: string; readonly latestDate: string; readonly under: number; readonly latestUnder: boolean };
  readonly checks: { readonly open: number; readonly closed: number; readonly names: string };
  readonly history: { readonly visits: number; readonly completed: number; readonly missed: number; readonly missedWord: string; readonly windowMonths: number };
  readonly coverage: { readonly status: string; readonly checked: string; readonly payer: string };
  readonly videoSlotsOpen: number;
}
export const PATIENTS = C<Readonly<Record<'linda', PatientRecord>>>('PATIENTS');
