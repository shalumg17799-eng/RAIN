/**
 * The six capability tags for RAIN's Use Case A conversations (spec "Radiant AI
 * capabilities mapping"): the callout each tag opens, and the copy for each
 * capability's architecture deep-dive. Use Case B carries no tags (plan D9).
 */
import { BP, CODING, CONTRACT, LOW_VALUE, MODEL, num, usdK } from './constants';

const PRIMARY = ['Synthetic claims', 'Synthetic EHR (FHIR R4)', 'MCO eligibility', 'Contract benchmark'];
const DEPLOYED = { deployedAt: 'Radiant Digital', deployedDesc: 'Cloud-neutral prototype; the data contract maps one to one onto API endpoints' };

export const CAPABILITY_CALLOUTS = [
  { trigger: 'briefing', capabilityName: 'Proactive Intelligence', eyebrow: 'RADIANT AI CAPABILITY', description: `Surfaces the contract checkpoint before anyone asks: cost ${CONTRACT.abovePct}% above expected, the quality gate at ${CONTRACT.gateMet} of ${CONTRACT.gateNeeded}, and model blind spots, each traced to its source.` },
  { trigger: 'converged', capabilityName: 'Converged Conversation', eyebrow: 'RADIANT AI CAPABILITY', description: 'One conversation across claims, EHR, eligibility, social needs, public county data and the contract benchmark, answered as one reconciled view.' },
  { trigger: 'friction', capabilityName: 'Friction Observability', eyebrow: 'RADIANT AI CAPABILITY', description: 'Shows where access breaks: drive time, no broadband, missed visits and unanswered reminders.' },
  { trigger: 'predictive', capabilityName: 'Predictive Intelligence', eyebrow: 'RADIANT AI CAPABILITY', description: 'Projects cost avoided, quality gate outcomes and county impact under different interventions, before the money is spent.' },
  { trigger: 'anomaly', capabilityName: 'Anomaly Detection', eyebrow: 'RADIANT AI CAPABILITY', description: `Finds outliers no single report shows: low-value imaging clustered at one site (${LOW_VALUE.winnemuccaRatePct}% against ${LOW_VALUE.networkRatePct}%), and a risk model ranking frontier patients ${MODEL.frontierGapPct}% too low.` },
  { trigger: 'action', capabilityName: 'Automated Action', eyebrow: 'RADIANT AI CAPABILITY', description: 'Produces worklists, campaigns, board and state briefs, and governance packets from the conversation. Nothing sends, books or publishes until a person approves.' },
];

export const CAPABILITY_DIAGRAMS = {
  proactive: {
    sourcesLabel: 'RAIN DATA SOURCES',
    primarySources: PRIMARY,
    secondarySources: ['eCQM engine', 'Low-value care library', 'HIE ADT feed', 'CDC PLACES'],
    ...DEPLOYED,
    bodyText: 'Each leader opens the day on the signals that matter to their role, read across claims, EHR, eligibility and the contract benchmark.',
    gapText: 'Payer reports arrive 45 days late, and nobody can say whether the gap is spending, coding or a few very sick patients.',
    withText: `The checkpoint on day one: $${CONTRACT.actualPmpm} against $${CONTRACT.expectedPmpm}, ${CONTRACT.gateMet} of ${CONTRACT.gateMeasures} measures, ${CONTRACT.daysLeft} days left.`,
    predictiveAI: [
      { name: 'Cost-versus-expected model', desc: 'PMPM gap split into coding, avoidable ED, low-value care and noise' },
      { name: 'Quality gate monitor', desc: 'eCQM results against contract targets, refreshed nightly' },
      { name: 'Model fairness check', desc: 'Subgroup results for the impactability score' },
    ],
    responsibleAI: ['Synthetic-data labelling', 'Small-cell suppression (under 11)', 'Human approval before any action', 'Subgroup check before release'],
  },
  converged: {
    sourcesLabel: 'RAIN DATA SOURCES',
    primarySources: PRIMARY,
    secondarySources: ['CDC PLACES', 'CDC SVI', 'HRSA HPSA', 'FCC Broadband Map'],
    ...DEPLOYED,
    connectorDesc: 'Claims, EHR, eligibility, social needs screening, 19 public sources',
    piiDesc: 'Member identifiers masked; state views aggregated and de-identified',
    bodyText: 'A plain-language question is answered across claims, EHR, eligibility, social needs and public county data at once.',
    gapText: 'Finance, quality and IT each hold part of the answer, in different reports on different calendars.',
    withText: 'The $26 gap in four parts, with every figure tied to its source.',
  },
  friction: {
    sourcesLabel: 'RAIN DATA SOURCES',
    primarySources: PRIMARY,
    secondarySources: ['OpenStreetMap drive time', 'FCC Broadband Map', 'Synthetic SMS logs', 'HRSA health center sites'],
    ...DEPLOYED,
    bodyText: 'Shows where access breaks: drive time, no broadband, missed visits and unanswered reminders, member by member.',
    adpSubtitle: 'One view of members, sites, drive times and channels',
    ontologyDesc: '"Near control" means a last reading within 10 points of target',
    enrichmentDesc: 'Adds drive time, broadband and language to every member',
    gapText: 'Patients who drive more than an hour miss visits at twice the rate, and nobody sees it until the slot is wasted.',
    withText: `${num(BP.telehealth)} members routed to telehealth with a home cuff instead of an hour-plus drive.`,
  },
  predictive: {
    sourcesLabel: 'RAIN DATA SOURCES',
    primarySources: PRIMARY,
    secondarySources: ['Impactability score', 'eCQM engine', 'Remote BP readings', 'RAIN cost model'],
    ...DEPLOYED,
    bodyText: 'Projects cost avoided, quality gate outcomes and county impact under each intervention before anyone commits.',
    predCards: [
      { name: 'Impactability score', desc: 'Ranks rising-risk members on how much an intervention can still change' },
      { name: 'Measure projection', desc: 'Where each quality measure lands by December 31 under each plan' },
      { name: 'Cost avoided', desc: 'Twelve-month avoided cost for the top-ranked outreach cohort' },
    ],
    signalSubtitle: 'Claims, EHR and remote readings, extended with access features',
    existingCard: { title: 'Payer reports (existing)', desc: 'Quarterly, 45 days late, no member detail' },
    agenticCardDesc: 'Feeds visit results and home readings back into every projection',
    gapText: 'Plans are made on last quarter\'s report, after the window to act has closed.',
    withText: `About ${BP.projected} members projected to reach control; ${BP.needed} passes the gate.`,
  },
  anomaly: {
    sourcesLabel: 'RAIN SIGNAL SOURCES',
    primarySources: PRIMARY,
    secondarySources: ['NPPES NPI Registry', 'EHR orders', 'Low-value care library', 'Census ZCTA'],
    ...DEPLOYED,
    bodyText: 'Finds deviations no single report shows: a site whose ordering jumps after a staffing change, a model that under-ranks a subgroup.',
    monitorAgents: [
      { name: 'Ordering monitor', desc: 'Low-value services per site and ordering clinician against the network rate' },
      { name: 'Subgroup monitor', desc: 'Risk ranks for frontier and town members with the same conditions and labs' },
      { name: 'Feed monitor', desc: 'Claims and ADT lag, matching failures and coverage gaps' },
      { name: 'Root cause', desc: 'Names the likely cause in plain language: a missing order set, a cost proxy' },
    ],
    gapText: `Low-value imaging worth ${usdK(LOW_VALUE.lbpImaging)} a year sits in claims for weeks before anyone sees the pattern.`,
    withText: `Winnemucca flagged at ${LOW_VALUE.winnemuccaRatePct}% against ${LOW_VALUE.networkRatePct}%, as a protocol gap, not a single provider.`,
  },
  action: {
    targetsLabel: 'RAIN EXECUTION TARGETS',
    primaryTargets: ['Care team worklist', 'Campaign builder', 'Board brief', 'Governance packet'],
    secondaryTargets: ['Scheduling', 'SMS reminders', 'State progress summary', 'Provider feedback notes'],
    ...DEPLOYED,
    bodyText: 'Drafts the worklist, campaign, brief or packet with its evidence attached. Nothing sends, books or publishes until a person approves.',
    gapText: 'Insights stop at a slide; outreach starts weeks later from a spreadsheet.',
    withText: `The ${num(BP.nearControl)}-member BP campaign and the ${CODING.members}-member coding list, ready for approval the same morning.`,
  },
};
