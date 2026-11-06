/**
 * The component catalog — the one list of what the AI can draw.
 *
 * This file is the source the backend's `GET /catalog` and
 * `docs/catalog/catalog.json` are generated from, so the API and the UI cannot
 * drift. Add a type here (with a schema and an example) and it can be drawn
 * from any persona's response; nothing else in the app changes.
 *
 * The gap ladder (docs/standard/README.md §3): pick an entry → extend it with
 * an optional prop → compose from tier 3 → create a new entry, once.
 */
import type { CatalogActions, CatalogEntry } from './types';
import * as S from './schemas';
import type { z } from 'zod';
import type { StandardSignal } from '../contract/signal';
import { toKitStatus } from '../contract/status';

type Props<T extends z.ZodType> = z.infer<T>;

/** Typed constructor: ties `example` and `adapt` to the schema. */
function entry<T extends z.ZodType>(e: Omit<CatalogEntry<Props<T>>, 'schema'> & { schema: T }): CatalogEntry {
  return e as unknown as CatalogEntry;
}

/** A contract value format → the KPI kit's `format(v)` function. */
function formatter(f?: Props<typeof S.valueFormat>) {
  if (!f) return undefined;
  return (v: number) => `${f.prefix ?? ''}${f.decimals !== undefined ? v.toFixed(f.decimals) : v}${f.suffix ?? ''}`;
}

/** The standard signal → the keys SignalCard reads. */
function toSignalCardSignal(s: StandardSignal) {
  return {
    id: s.id,
    title: s.title,
    description: s.description,
    severity: { good: 'healthy', warning: 'warning', critical: 'critical', info: 'info', neutral: 'info' }[s.status],
    affected_count: s.affectedCount,
    sources: s.sources.length ? s.sources : undefined,
    trend: s.trend,
    confidence: s.confidence,
    action: s.action,
  };
}

const exampleSignal: StandardSignal = {
  id: 'SIG-EXAMPLE-1',
  title: 'Mortgage applications dropped 18% week over week',
  description: 'Abandonment concentrates at the income-verification step for first-time buyers.',
  status: 'critical',
  affectedCount: 1240,
  sources: ['Core banking', 'Web analytics'],
  trend: 'worsening',
  confidence: { score: 91 },
  action: 'Offer assisted verification to first-time buyers this week',
};

export const CATALOG: CatalogEntry[] = [
  // ── Tier 2 · catalog components ────────────────────────────────────
  entry({
    type: 'signal_card', version: 1, tier: 2, title: 'Signal card',
    description: 'One proactively surfaced insight: what changed, how bad, who is affected, the evidence and the next step. Use when the answer is about a single issue the persona should act on.',
    schema: S.signalCardProps,
    example: { signal: exampleSignal, showAction: true },
    load: () => import('@/components/cards/SignalCard'),
    adapt: (p) => ({ ...p, signal: toSignalCardSignal(p.signal) }),
  }),
  entry({
    type: 'action_cards', version: 1, tier: 2, title: 'Action cards',
    description: 'Recommended actions the persona can confirm, each with the system it runs in and a confidence score. Use when the answer ends in something to do.',
    schema: S.actionCardsProps,
    example: { actions: [
      { id: 'ACT-1', title: 'Open a JIRA ticket for the verification step', description: 'Assign to digital lending; due Friday.', system: 'JIRA', confidence: 88 },
      { id: 'ACT-2', title: 'Schedule a callback campaign', description: '1,240 members, staggered over three days.', system: 'Calendar / Salesforce', confidence: 82 },
    ] },
    load: () => import('./adapters/ActionCardList'),
    adapt: (p, actions: CatalogActions) => ({ ...p, onAction: actions.onAction }),
  }),
  entry({
    type: 'metric_card', version: 1, tier: 2, title: 'Metric card',
    description: 'One measure with its status against target, trend in words and a sparkline. Use for a single KPI, or several inside a grid.',
    schema: S.metricCardProps,
    example: { title: 'Time to disposition', figure: '83%', words: 'Civil unlimited', period: 'Sep 2026', status: 'warning', statusLabel: 'Below target', trend: { dir: 'down', tone: 'worsening', delta: '−4 pts', word: 'Worsening' }, series: [88, 87, 86, 85, 83], target: 90 },
    load: () => import('@/components/kpi/MetricCard'),
    adapt: (p) => ({ ...p, status: p.status && toKitStatus(p.status) }),
  }),
  entry({
    type: 'trend_chart', version: 1, tier: 2, title: 'Trend chart',
    description: 'A measure over time with an optional target line and a one-line summary; includes a table view for accessibility. Use when the answer is about how something moved.',
    schema: S.trendChartProps,
    example: { points: [{ label: 'Jun', value: 12 }, { label: 'Jul', value: 14 }, { label: 'Aug', value: 17 }, { label: 'Sep', value: 21 }], format: { suffix: ' min' }, target: 15, targetLabel: 'Target', summary: 'Wait time rose for three months straight and is now 6 minutes over target.', tone: 'worsening' },
    load: () => import('@/components/kpi/TrendChart'),
    adapt: (p) => ({ ...p, format: formatter(p.format) }),
  }),
  entry({
    type: 'target_bar', version: 1, tier: 2, title: 'Target bar',
    description: 'Where one value sits against its target on a single track (a bullet chart). Use for "x against a y target".',
    schema: S.targetBarProps,
    example: { value: 73, target: 95, percent: true, status: 'critical', valueLabel: '73% resolved', targetLabel: '95% floor' },
    load: () => import('@/components/kpi/TargetBar'),
    adapt: (p) => ({ ...p, status: p.status && toKitStatus(p.status) }),
  }),
  entry({
    type: 'peer_bar', version: 1, tier: 2, title: 'Peer bar',
    description: 'One site\'s value against its peers\' median on a shared scale. Use inside comparisons.',
    schema: S.peerBarProps,
    example: { value: 64, peer: 71, min: 0, max: 100, higherIsBetter: true, valueLabel: '64%' },
    load: () => import('@/components/kpi/PeerBar'),
  }),
  entry({
    type: 'status_summary', version: 1, tier: 2, title: 'Status summary',
    description: 'How a set of measures stands at a glance: counts per status, a proportional bar, and the names of the worst. Use for portfolio questions.',
    schema: S.statusSummaryProps,
    example: { title: 'Measures this month', segments: [{ key: 'off', label: 'Off target', count: 3, status: 'critical' }, { key: 'watch', label: 'Watch', count: 5, status: 'warning' }, { key: 'on', label: 'On target', count: 12, status: 'good' }], worst: { label: 'Off target', items: [{ label: 'Time to disposition' }, { label: 'Backlog age' }, { label: 'Juror yield' }] } },
    load: () => import('@/components/kpi/StatusSummary'),
    adapt: (p) => ({ ...p, segments: p.segments.map((g) => ({ ...g, status: toKitStatus(g.status) })) }),
  }),
  entry({
    type: 'kpi_table', version: 1, tier: 2, title: 'KPI table',
    description: 'Several measures compared in aligned columns: measure, latest, status, change. Use when comparing three or more KPIs.',
    schema: S.kpiTableProps,
    example: { rows: [
      { key: 'ttd', name: 'Time to disposition', figure: '83%', period: 'Sep 2026', status: 'warning', statusLabel: 'Below target', trend: { dir: 'down', tone: 'worsening', delta: '−4 pts', word: 'Worsening' } },
      { key: 'csat', name: 'Court experience index', figure: '78', period: 'Q3', status: 'good', statusLabel: 'On target', trend: { dir: 'up', tone: 'improving', delta: '+3', word: 'Improving' } },
    ] },
    load: () => import('@/components/kpi/KpiTable'),
    adapt: (p) => ({ ...p, rows: p.rows.map((r) => ({ ...r, status: toKitStatus(r.status) })) }),
  }),

  entry({
    type: 'current_state_diagram', version: 1, tier: 2, title: 'Current-state process',
    description: 'How a piece of work runs today, step by step — which steps sit in a system and which fall in a gap — with the intervention that closes each gap. Use when the answer explains "how does this work today?".',
    schema: S.currentStateProps,
    example: { productName: 'the platform', data: {
      title: 'How a permit is verified today', subtitle: 'Four steps, two outside any system.', illustrative: true,
      steps: [
        { id: 's1', label: 'Permit issued', detail: 'Issuer signs the paper permit.', state: 'system', system: 'Permit-to-work' },
        { id: 's2', label: 'Crew starts work', detail: 'Nobody confirms the crew is the one on the permit.', state: 'gap' },
        { id: 's3', label: 'Gas test logged', detail: 'Logged after the fact, by hand.', state: 'manual' },
        { id: 's4', label: 'Permit closed', state: 'system', system: 'Permit-to-work' },
      ],
      gapSummary: 'Two of four steps happen outside any system.',
      interventions: [{ id: 'i1', stepId: 's2', currentStep: 'Crew starts work', intervention: 'Match tags in the zone to the permit crew', capability: 'Anomaly detection', impact: 'Unpermitted work flagged in minutes' }],
    } },
    load: () => import('@/components/process/CurrentStateDiagram'),
  }),
  entry({
    type: 'journey_map', version: 1, tier: 2, title: 'Journey map',
    description: 'A persona\'s day or cycle as phases, each with its emotion, pain points and the opportunity, traced to the signals that answer them. Use when the answer walks through someone\'s experience end to end.',
    schema: S.journeyMapProps,
    example: { title: 'Shift supervisor — handover day', data: {
      scenario: 'Handover day', timeframe: 'One shift', baselineSatisfaction: 4, baselineNote: 'Satisfaction with handover today', illustrative: true,
      phases: [
        { id: 'p1', index: 1, name: 'Arrive', emotion: 3, emotionLabel: 'Neutral', touchpoints: ['Gate', 'Control room'], action: 'Reads the overnight log', thought: 'What changed while I was off?', painPoints: ['No view of open permits'], opportunity: 'A briefing ready on arrival' },
        { id: 'p2', index: 2, name: 'Muster drill', emotion: 1, emotionLabel: 'Anxious', touchpoints: ['Muster point'], action: 'Counts heads by clipboard', thought: 'Is anyone missing?', painPoints: ['Headcount by clipboard'], opportunity: 'Live headcount by zone', momentOfTruth: true, momentLabel: 'Moment of truth' },
      ],
      traceability: [{ phase: 'Muster drill', painPoint: 'Headcount by clipboard', signal: 'Muster time above target' }],
    } },
    load: () => import('@/components/process/JourneyMap'),
  }),

  entry({
    type: 'stat_tiles', version: 1, tier: 2, title: 'KPI tiles',
    description: 'A row of headline figures, each with a short trend line; a tile with a chip asks that question when clicked. Use for the persona\'s at-a-glance numbers.',
    schema: S.statTilesProps,
    example: { stats: [
      { id: 'members', label: 'Members', value: '84,000', trend: '+1.2% this quarter', positive: true, icon: 'users', iconTone: 'brand' },
      { id: 'lts', label: 'Loan-to-share', value: '89.7%', trend: 'Rising toward the 90% ceiling', positive: false, icon: 'gauge', iconTone: 'warning', chipText: 'Why is loan-to-share rising?' },
      { id: 'nw', label: 'Net worth ratio', value: '9.62%', trend: 'Well capitalized', positive: true, icon: 'shield-check', iconTone: 'good' },
    ] },
    load: () => import('@/components/cards/DataOverviewBar'),
    adapt: (p, actions) => ({ ...p, visible: true, onStatClick: (chip: string) => actions.onChip?.(chip) }),
  }),
  entry({
    type: 'hero_metric', version: 1, tier: 2, title: 'Hero metric',
    description: 'The one number to look at first, on the brand surface: figure, status, trend, why it leads, its trend line and target. Use once per answer, for the headline measure.',
    schema: S.heroMetricProps,
    example: { eyebrow: 'Headline measure', title: 'Time to disposition', figure: '83%', words: 'of civil unlimited cases', period: 'Sep 2026', status: 'warning', statusLabel: 'Below target', trend: { dir: 'down', tone: 'worsening', delta: '−4 pts', word: 'Worsening' }, why: 'Four points under the 90% target and falling for three months.', series: [88, 87, 86, 85, 83], target: 90, seriesFrom: 'May', seriesTo: 'Sep' },
    load: () => import('@/components/kpi/HeroMetric'),
    adapt: (p) => ({ ...p, status: p.status && toKitStatus(p.status) }),
  }),
  entry({
    type: 'gauge', version: 1, tier: 2, title: 'Gauge',
    description: 'A half-donut score from 0 to 100, coloured by its state. Use for a readiness or health score; always print the number beside it.',
    schema: S.gaugeProps,
    example: { score: 78, status: 'warning', size: 72 },
    load: () => import('@/components/charts/MiniGauge'),
    adapt: (p) => ({ ...p, status: ({ good: 'green', warning: 'amber', critical: 'red', info: 'amber', neutral: 'amber' } as const)[p.status] }),
  }),
  entry({
    type: 'signal_tile', version: 1, tier: 2, title: 'Signal tile',
    description: 'One signal as a compact clickable tile: state accent, title and confidence. Use for a row of insights; use signal_card when the answer is about one issue in depth.',
    schema: S.signalTileProps,
    example: { signal: exampleSignal },
    load: () => import('@/components/cards/InsightMiniCard'),
    adapt: (p, actions) => ({ signal: toSignalCardSignal(p.signal), onClick: () => actions.onChip?.(p.signal.title) }),
  }),
  // ── Tier 3 · compose building blocks ───────────────────────────────
  entry({
    type: 'stack', version: 1, tier: 3, title: 'Stack',
    description: 'Lays out child components top to bottom. Use to group several components into one answer.',
    schema: S.stackProps,
    example: { children: [{ type: 'text', version: 1, props: { text: 'Two things changed overnight.' } }, { type: 'callout', version: 1, props: { title: 'Queue wait is 6 minutes over target', status: 'warning' } }] },
    load: () => import('./adapters/StackEntry'),
  }),
  entry({
    type: 'grid', version: 1, tier: 3, title: 'Grid',
    description: 'Lays out child components in 1–4 responsive columns. Use for tiles side by side.',
    schema: S.gridProps,
    example: { columns: 2, children: [{ type: 'stat', version: 1, props: { label: 'Members affected', value: '1,240', status: 'critical' } }, { type: 'stat', version: 1, props: { label: 'Revenue at risk', value: '$2.4M', status: 'warning' } }] },
    load: () => import('./adapters/GridEntry'),
  }),
  entry({
    type: 'text', version: 1, tier: 3, title: 'Text',
    description: 'A paragraph of plain text inside a composed answer.',
    schema: S.textProps,
    example: { text: 'Abandonment concentrates at income verification.' },
    load: () => import('./adapters/TextEntry'),
  }),
  entry({
    type: 'callout', version: 1, tier: 3, title: 'Callout',
    description: 'A highlighted statement with a status colour: a warning, a finding, a confirmation.',
    schema: S.calloutProps,
    example: { title: 'Two systems disagree on the deposit total', body: 'The general ledger is $1.2M above the core system for the merged division.', status: 'warning' },
    load: () => import('./adapters/CalloutEntry'),
  }),
  entry({
    type: 'stat', version: 1, tier: 3, title: 'Stat',
    description: 'One figure with a label, optional status, trend and icon. Use inside a grid for tiles.',
    schema: S.statProps,
    example: { label: 'Members affected', value: '1,240', status: 'critical', trend: { direction: 'up', label: '+18% WoW', good: false }, icon: 'users' },
    load: () => import('./adapters/StatEntry'),
  }),
  entry({
    type: 'data_table', version: 1, tier: 3, title: 'Data table',
    description: 'Rows and columns of data; a status column draws as badges. Use for lists of records.',
    schema: S.dataTableProps,
    example: { columns: [{ key: 'branch', label: 'Branch' }, { key: 'wait', label: 'Wait (min)', kind: 'number' }, { key: 'state', label: 'Status', kind: 'status' }], rows: [{ branch: 'Norfolk', wait: 21, state: 'critical' }, { branch: 'Pensacola', wait: 14, state: 'warning' }, { branch: 'San Diego', wait: 8, state: 'good' }] },
    load: () => import('./adapters/DataTableEntry'),
  }),
  entry({
    type: 'chart', version: 1, tier: 3, title: 'Chart',
    description: 'A line or bar chart of one or more series. Use when no tier 2 chart fits the data.',
    schema: S.chartProps,
    example: { kind: 'bar', unit: '%', title: 'Abandonment by step', series: [{ name: 'This week', points: [{ label: 'Start', value: 4 }, { label: 'Income', value: 19 }, { label: 'Review', value: 7 }] }] },
    load: () => import('./adapters/ChartEntry'),
  }),
  entry({
    type: 'status_badge', version: 1, tier: 3, title: 'Status badge',
    description: 'A state in words with an icon and token colour. Accepts any status spelling.',
    schema: S.statusBadgeProps,
    example: { status: 'warning', label: 'Watch' },
    load: () => import('@/components/common/StatusBadge'),
  }),
  entry({
    type: 'sparkline', version: 1, tier: 3, title: 'Sparkline',
    description: 'A small trend line coloured by what the move means. Decorative: pair it with words.',
    schema: S.sparklineProps,
    example: { values: [4, 5, 5, 7, 9], tone: 'worsening' },
    load: () => import('@/components/kpi/Sparkline'),
  }),
  entry({
    type: 'confidence_badge', version: 1, tier: 3, title: 'Confidence badge',
    description: 'The AI\'s confidence in an answer, 0–100, with an optional note.',
    schema: S.confidenceBadgeProps,
    example: { score: 87, note: 'Two of three sources agree.' },
    load: () => import('@/components/common/ConfidenceBadge'),
  }),
  entry({
    type: 'illustrative_note', version: 1, tier: 3, title: 'Illustrative-data note',
    description: 'Marks figures as illustrative rather than sourced. Use beside any invented number.',
    schema: S.illustrativeNoteProps,
    example: { note: 'Figures are illustrative.' },
    load: () => import('@/components/common/IllustrativeDataChip'),
  }),
];

const byType = new Map(CATALOG.map((e) => [e.type, e]));

export function getCatalogEntry(type: string): CatalogEntry | undefined {
  return byType.get(type);
}

export function listCatalog(): CatalogEntry[] {
  return CATALOG;
}
