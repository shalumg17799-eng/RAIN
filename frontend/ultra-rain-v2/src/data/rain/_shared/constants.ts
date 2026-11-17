/**
 * RAIN master numbers: the Q3 value-based contract checkpoint at Sierra Basin
 * Community Health (a fictional FQHC network). Every value here comes from the
 * backend (GET /api/v4/ui2/data, section "constants"): the RAIN v0.4 backend
 * computes them per request from the row-level synthetic data in
 * rain_v4.synthetic and the public data in rain_v4.public_data
 * (rain-api/metrics_v4.py), and adds this UI's extras (rain-api/ui2_v4.py). This
 * module only types them and keeps the formatting helpers. The county public
 * fields (htnPct, diabetesPct, svi, hpsa) are live public data (CDC PLACES,
 * CDC/ATSDR SVI, HRSA).
 */
import { rainValue } from './backendData';

const C = <T,>(key: string) => rainValue<T>('constants', key);

export type PersonaKey = 'ceo' | 'cmo' | 'cio' | 'state' | 'chw' | 'access';
export type MeasureId = 'CMS2' | 'CMS125' | 'CMS165' | 'CMS122' | 'CMS130';
export type CountyId = 'elko' | 'humboldt' | 'lander' | 'pershing' | 'whitePine' | 'churchill';

export const ILLUSTRATIVE = C<string>('ILLUSTRATIVE');

/** Persona key → id, in the switcher's order (plan D1): the six operators. */
export const PERSONAS = C<Readonly<Record<PersonaKey, string>>>('PERSONAS');
/** Linda Garcia, the patient (Use Case C): a persona, but not an operator, so not a contract key above. */
export const PATIENT_PERSONA_ID = C<string>('PATIENT_PERSONA_ID');

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

/** The PMPM gap in four parts. */
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
  readonly syntheticSources: number; readonly adtLag: string;
  /** Ranking accuracy against the clinical review sample. */
  readonly auc: number;
  readonly unmatchedRecords: number;
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

/** A blood pressure reading. */
export interface BpReading {
  readonly sys: number;
  readonly dia: number;
}

/**
 * Linda Garcia, the patient (spec v2.1, Use Case C). Computed by the backend from
 * her own rows (name, age, town, drive, last reading, next visit, member id), with
 * the facts of her phone view (goal, readings she shares, refill, mobile clinic)
 * from the new UI's configuration. Bilingual: her phone view opens in English.
 */
export const LINDA = C<{
  readonly name: string; readonly first: string; readonly age: number; readonly town: string; readonly clinic: string;
  readonly driveMin: number; readonly bp: string; readonly bpMonth: string; readonly monthsSinceVisit: number;
  readonly missedVisits: number; readonly language: string; readonly languages: string; readonly reading: string;
  readonly link: string; readonly memberId: string;
  readonly goal: BpReading;
  readonly last: BpReading & { readonly month: { readonly en: string; readonly es: string } };
  readonly earlier: BpReading;
  readonly home: BpReading;
  readonly visitReading: BpReading;
  /** A reading at or above either number shows the clinic's fixed safety message. */
  readonly urgent: BpReading;
  readonly visit: { readonly day: string; readonly date: string; readonly time: string; readonly es: string; readonly esDay: string; readonly esDate: string };
  readonly refill: { readonly drug: string; readonly due: string; readonly arrives: string };
  readonly mobileClinic: { readonly day: string; readonly date: string; readonly time: string; readonly driveMin: number };
  readonly site: string;
}>('LINDA');

/** "142/88" for a reading. */
export const bpText = (r: { sys: number; dia: number }) => `${r.sys}/${r.dia}`;

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

/** Primary care visits indexed to January = 100 (monthly path illustrative; September is the reported change for Lander and Pershing). */
export const PC_TREND = C<{ readonly months: ReadonlyArray<string>; readonly landerPershing: ReadonlyArray<number>; readonly otherFour: ReadonlyArray<number> }>('PC_TREND');

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
