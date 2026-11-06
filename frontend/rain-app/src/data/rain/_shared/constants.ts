/**
 * RAIN v2 master numbers: the Q3 value-based contract checkpoint at Sierra
 * Basin Community Health (a fictional FQHC network). Defined once here; the
 * per-persona JSON contracts, the workbenches and the cards all quote these,
 * and `rain.test.ts` fails if a JSON figure drifts from them.
 *
 * Figures the spec gives are marked SPEC. Everything else is illustrative
 * synthetic data, chosen so the spec's totals still reconcile, and labelled
 * "Synthetic" on screen (plan D21).
 */

export const ILLUSTRATIVE = 'Synthetic data for a demo. Sierra Basin Community Health, High Desert Health Plan and every person shown are fictional.';

/** Persona key → id, in the switcher's order (plan D1). */
export const PERSONAS = {
  ceo: 'rain_ceo',
  cmo: 'rain_cmo',
  cio: 'rain_cio',
  state: 'rain_state',
  chw: 'rain_chw',
  access: 'rain_access',
} as const;
export type PersonaKey = keyof typeof PERSONAS;

export const ORG = {
  network: 'Sierra Basin Community Health',
  networkShort: 'Sierra Basin',
  plan: 'High Desert Health Plan',
  program: 'Rural Health Outcomes Accelerator',
  product: 'Ask AI',
} as const;

// ─── Formatting ─────────────────────────────────────────────────────────────

export const num = (n: number) => n.toLocaleString('en-US');
export const usd = (n: number, digits = 0) => `$${n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
export const usdK = (n: number) => `$${Math.round(n / 1000).toLocaleString('en-US')}K`;
export const usdM = (n: number, digits = 1) => `$${(n / 1_000_000).toFixed(digits)}M`;

// ─── The contract (SPEC) ────────────────────────────────────────────────────

export const CONTRACT = {
  members: 9400,
  actualPmpm: 412,
  expectedPmpm: 386,
  abovePct: 6.7,
  annualGap: 2_900_000,
  daysLeft: 58,
  gateNeeded: 3,
  gateMeasures: 5,
  gateMet: 2,
  claimsLagDays: 45,
} as const;

/** The $26 PMPM gap in four parts (SPEC). */
export const GAP = [
  { id: 'coding', label: 'Coding gap', value: 12, note: 'Not spending: 73 high-need members not yet recaptured' },
  { id: 'ed', label: 'Excess avoidable ED', value: 8, note: '312 visits per 1,000 against 251' },
  { id: 'lowValue', label: 'Low-value care', value: 5.5, note: '2,140 services across 14 measures' },
  { id: 'other', label: 'Other', value: 0.5, note: 'Noise' },
] as const;
export const GAP_TOTAL = GAP.reduce((s, g) => s + g.value, 0);

/** Segmentation by impactability (SPEC counts; share of spend for the last two is illustrative). */
export const SEGMENTS = [
  { id: 'highNeed', label: 'High-need, high-cost', members: 236, sharePct: 2.5, spendPct: 41, action: 'Care plan intensity, risk-coding recapture' },
  { id: 'impactable', label: 'Impactable, rising risk', members: 1180, sharePct: 12.6, spendPct: 27, action: 'Ranked outreach, top 300 first' },
  { id: 'stable', label: 'Low risk, stable', members: 7984, sharePct: 84.9, spendPct: 32, action: 'Light-touch reminders' },
] as const;

export const COHORT = { topRanked: 300, avoidedCost12m: 1_100_000 } as const;

export const CODING = { members: 73, ofHighNeed: 236, sharePct: 31, understatedPct: 3.1, correctedBenchmark: 398, gapAfterPct: 3.5 } as const;

export const LOW_VALUE = {
  services: 2140,
  annual: 618_000,
  measures: 14,
  lbpImaging: 162_000,
  winnemuccaSharePct: 71,
  networkRatePct: 9,
  winnemuccaRatePct: 27,
  rotationMonth: 'April',
  clinicians: 3,
} as const;

export const ED = { per1000: 312, benchmark: 251 } as const;

/** The five gate measures (SPEC). `higherIsBetter: false` for HbA1c poor control. */
export const MEASURES = [
  { id: 'CMS2', name: 'Depression screening', current: 74, target: 70, higherIsBetter: true, projected: 75 },
  { id: 'CMS125', name: 'Breast cancer screening', current: 52, target: 50, higherIsBetter: true, projected: 53 },
  { id: 'CMS165', name: 'Controlling high blood pressure', current: 58, target: 65, higherIsBetter: true, projected: 66 },
  { id: 'CMS122', name: 'HbA1c poor control (over 9%)', current: 34, target: 30, higherIsBetter: false, projected: 33 },
  { id: 'CMS130', name: 'Colorectal cancer screening', current: 33, target: 40, higherIsBetter: true, projected: 37 },
] as const;
export type MeasureId = (typeof MEASURES)[number]['id'];
export const isMet = (m: { current: number; target: number; higherIsBetter: boolean }) => (m.higherIsBetter ? m.current >= m.target : m.current <= m.target);

/** The blood pressure campaign (SPEC). */
export const BP = {
  hypertensive: 2250,
  nearControl: 412,
  withinPoints: 10,
  needed: 180,
  projected: 210,
  inPerson: 144,
  telehealth: 268,
  cuffsToShip: 37,
  shortPts: 7,
} as const;

export const FIT = { gainPts: 4 } as const;

// ─── CIO (SPEC) ─────────────────────────────────────────────────────────────

export const MODEL = {
  name: 'Impactability score',
  version: 'v1.3',
  candidate: 'v1.4',
  frontierGapPct: 18,
  frontierGapAfterPct: 3,
  releaseThresholdPct: 5,
  missingFromTop: 57,
  inBpDenominator: 41,
  fewerVisitsPct: 31,
  medianDriveMin: 74,
  noBroadband: 190,
  socialScreenedPct: 38,
  publicSources: 19,
  syntheticSources: 6,
  adtLag: 'Under 1 hour',
  /** Ranking accuracy against the clinical review sample (illustrative). */
  auc: 0.81,
  unmatchedRecords: 214,
} as const;

// ─── State (SPEC) ───────────────────────────────────────────────────────────

export const STATE = {
  networks: 4,
  sites: 18,
  members: 31_600,
  counties: 6,
  hpsaCounties: 6,
  edPer1000: 298,
  lowValue: 2_400_000,
  pcVisitDropPct: 14,
  lowBroadbandZips: 6,
  broadbandFloorPct: 40,
  suppressUnder: 11,
  optionAEdCutPct: 12,
} as const;

// ─── Care team (SPEC) ───────────────────────────────────────────────────────

export const CARE = {
  teresaTop: 46,
  teresaNoCallback: 5,
  teresaOpen: 200,
  booked: 62,
  controlled: 18,
  brandonBookings: 23,
  brandonUnconfirmed: 9,
  brandonRReplies: 4,
  telehealthProviders: 2,
} as const;

export const LINDA = {
  name: 'Linda Garcia',
  first: 'Linda',
  age: 58,
  town: 'Battle Mountain',
  driveMin: 81,
  bp: '148/92',
  bpMonth: 'August',
  monthsSinceVisit: 7,
  missedVisits: 2,
  language: 'Spanish',
  reading: '132/84',
  visit: { day: 'Thursday', date: 'Nov 5', time: '2:00 PM', es: 'el jueves 5 de nov. a las 2:00 PM' },
} as const;

// ─── Sites and counties (illustrative; plan D17) ────────────────────────────

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

export type CountyId = 'elko' | 'humboldt' | 'lander' | 'pershing' | 'whitePine' | 'churchill';

export const SITES: Site[] = [
  { id: 'elko', name: 'Elko', county: 'elko', members: 2300, pmpm: 398, imagingPct: 5, lowValue: 120_000, locum: false },
  { id: 'wells', name: 'Wells', county: 'elko', members: 600, pmpm: 421, imagingPct: 4, lowValue: 36_000, locum: false },
  { id: 'winnemucca', name: 'Winnemucca', county: 'humboldt', members: 1700, pmpm: 431, imagingPct: 27, lowValue: 196_000, locum: true },
  { id: 'battleMountain', name: 'Battle Mountain', county: 'lander', members: 1000, pmpm: 437, imagingPct: 6, lowValue: 54_000, locum: false },
  { id: 'lovelock', name: 'Lovelock', county: 'pershing', members: 700, pmpm: 426, imagingPct: 7, lowValue: 52_000, locum: true },
  { id: 'ely', name: 'Ely', county: 'whitePine', members: 1100, pmpm: 404, imagingPct: 5, lowValue: 62_000, locum: false },
  { id: 'fallon', name: 'Fallon', county: 'churchill', members: 2000, pmpm: 396, imagingPct: 4, lowValue: 98_000, locum: false },
];
export const siteById = (id: string) => SITES.find((s) => s.id === id);

/** PMPM by month since January (illustrative; averages $412). */
export const PMPM_TREND = [
  { month: 'Jan', actual: 401 },
  { month: 'Feb', actual: 405 },
  { month: 'Mar', actual: 409 },
  { month: 'Apr', actual: 410 },
  { month: 'May', actual: 414 },
  { month: 'Jun', actual: 416 },
  { month: 'Jul', actual: 415 },
  { month: 'Aug', actual: 418 },
  { month: 'Sep', actual: 420 },
] as const;

/** Winnemucca low back pain imaging rate by month (illustrative; Apr to Sep averages 27%). */
export const WINNEMUCCA_TREND = [
  { month: 'Jan', value: 8 },
  { month: 'Feb', value: 9 },
  { month: 'Mar', value: 8 },
  { month: 'Apr', value: 24 },
  { month: 'May', value: 27 },
  { month: 'Jun', value: 29 },
  { month: 'Jul', value: 28 },
  { month: 'Aug', value: 27 },
  { month: 'Sep', value: 28 },
] as const;

/** The three rotating clinicians at Winnemucca, de-identified (illustrative). */
export const LOCUMS = [
  { id: 'Locum clinician 1', ratePct: 27, orders: 41 },
  { id: 'Locum clinician 2', ratePct: 28, orders: 38 },
  { id: 'Locum clinician 3', ratePct: 26, orders: 35 },
] as const;

/** The 14-measure low-value care library (illustrative split of the SPEC totals). */
export const LV_MEASURES = [
  { id: 'LV01', name: 'Imaging for uncomplicated low back pain', basis: 'Choosing Wisely', services: 410, dollars: 162_000 },
  { id: 'LV02', name: 'Vitamin D screening in low-risk adults', basis: 'Choosing Wisely', services: 520, dollars: 96_000 },
  { id: 'LV03', name: 'Preoperative testing before low-risk surgery', basis: 'Choosing Wisely', services: 260, dollars: 88_000 },
  { id: 'LV04', name: 'Annual EKG in low-risk adults', basis: 'USPSTF', services: 300, dollars: 64_000 },
  { id: 'LV05', name: 'Imaging for uncomplicated headache', basis: 'Choosing Wisely', services: 120, dollars: 58_000 },
  { id: 'LV06', name: 'Arthroscopic knee surgery for osteoarthritis', basis: 'Choosing Wisely', services: 15, dollars: 30_000 },
  { id: 'LV07', name: 'Antibiotics for acute upper respiratory infection', basis: 'Choosing Wisely', services: 190, dollars: 22_000 },
  { id: 'LV08', name: 'Colorectal screening after age 85', basis: 'USPSTF', services: 25, dollars: 21_000 },
  { id: 'LV09', name: 'Head imaging for simple fainting', basis: 'Choosing Wisely', services: 30, dollars: 19_000 },
  { id: 'LV10', name: 'Cervical screening after age 65 at low risk', basis: 'USPSTF', services: 55, dollars: 16_000 },
  { id: 'LV11', name: 'PSA screening after age 70', basis: 'USPSTF', services: 70, dollars: 14_000 },
  { id: 'LV12', name: 'Repeat bone density test within 2 years', basis: 'Choosing Wisely', services: 40, dollars: 11_000 },
  { id: 'LV13', name: 'Thyroid screening in adults without symptoms', basis: 'USPSTF', services: 60, dollars: 9_000 },
  { id: 'LV14', name: 'Opioids first for acute low back pain', basis: 'Choosing Wisely', services: 45, dollars: 8_000 },
] as const;

/** Six-county state view (illustrative values; members and ED reconcile to SPEC totals). */
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
}

export const COUNTIES: County[] = [
  { id: 'elko', name: 'Elko', members: 9800, htnPct: 29, diabetesPct: 10, svi: 0.41, hpsa: 'Part of county', broadbandPct: 78, pcVisitChangePct: -3, edPer1000: 285, lowValue: 640_000, heartFailure: 214, bpControlPct: 61 },
  { id: 'humboldt', name: 'Humboldt', members: 5200, htnPct: 31, diabetesPct: 11, svi: 0.55, hpsa: 'Part of county', broadbandPct: 71, pcVisitChangePct: -5, edPer1000: 296, lowValue: 520_000, heartFailure: 96, bpControlPct: 58 },
  { id: 'lander', name: 'Lander', members: 2900, htnPct: 34, diabetesPct: 13, svi: 0.62, hpsa: 'Whole county', broadbandPct: 58, pcVisitChangePct: -14, edPer1000: 352, lowValue: 290_000, heartFailure: 31, bpControlPct: 53 },
  { id: 'pershing', name: 'Pershing', members: 2100, htnPct: 35, diabetesPct: 13, svi: 0.71, hpsa: 'Whole county', broadbandPct: 52, pcVisitChangePct: -14, edPer1000: 341, lowValue: 210_000, heartFailure: 8, bpControlPct: 52 },
  { id: 'whitePine', name: 'White Pine', members: 3700, htnPct: 33, diabetesPct: 12, svi: 0.48, hpsa: 'Part of county', broadbandPct: 66, pcVisitChangePct: -4, edPer1000: 289, lowValue: 260_000, heartFailure: 47, bpControlPct: 60 },
  { id: 'churchill', name: 'Churchill', members: 7900, htnPct: 32, diabetesPct: 12, svi: 0.52, hpsa: 'Part of county', broadbandPct: 84, pcVisitChangePct: -2, edPer1000: 288, lowValue: 480_000, heartFailure: 152, bpControlPct: 62 },
];
export const countyById = (id: string) => COUNTIES.find((c) => c.id === id);

/** A count under the state's privacy floor is shown as a dash. */
export const suppress = (n: number) => (n < STATE.suppressUnder ? '–' : num(n));

/** The four participating networks (illustrative; 18 sites). */
export const NETWORKS = [
  { id: 'sbch', name: 'Sierra Basin Community Health', sites: 7, bpControlPct: 58, colorectalPct: 33, edPer1000: 312 },
  { id: 'gbrc', name: 'Great Basin Rural Clinics', sites: 4, bpControlPct: 61, colorectalPct: 36, edPer1000: 289 },
  { id: 'hrhp', name: 'Humboldt River Health Partners', sites: 3, bpControlPct: 55, colorectalPct: 31, edPer1000: 301 },
  { id: 'rvfh', name: 'Ruby Valley Family Health', sites: 4, bpControlPct: 63, colorectalPct: 38, edPer1000: 284 },
] as const;

/** The three funding options (SPEC outcomes; reach and cost illustrative). */
export const OPTIONS = [
  { id: 'A', name: 'Care coordinators and telehealth rechecks in Lander and Pershing', reach: 5000, cost: 1_400_000, outcome: 'Recover most lost primary care visits; avoidable ED down about 12% there', time: 'Within a year', impact: 'Largest health impact' },
  { id: 'B', name: 'Shared low-value care feedback, all four networks', reach: 31_600, cost: 0, outcome: 'Cut about a third of the $2.4M', time: '3 to 6 months', impact: 'Fastest cost return' },
  { id: 'C', name: 'Mobile clinic days in the six low-broadband ZIP areas', reach: 1900, cost: 600_000, outcome: 'Access floor that option A depends on', time: '6 months', impact: 'Access floor' },
] as const;

/** The six low-broadband ZIP areas (named by town; illustrative). */
export const LOW_BB_PLACES = ['Jarbidge', 'Denio', 'Austin', 'Imlay', 'Baker', 'Owyhee'] as const;

/** Data freshness, shown on every Use Case A view. */
export const FRESHNESS = 'Claims through Q3 (45-day lag) · ADT today';
