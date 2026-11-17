/**
 * The RAIN data contract (spec "Data contract (JSON now, API later)"): one JSON
 * file per operator persona with exactly seven top-level keys. A step names
 * its visuals by id and may carry a `launch` (workbench id and filter). No
 * file reads a value from another file to fetch a third, so a backend swaps
 * each file for one endpoint (GET /personas/:id/contract) with no change here.
 */
import type { CapabilityId, NavKey } from '@core/types';

export const CONTRACT_KEYS = ['signals', 'kpis', 'steps', 'queries', 'viz', 'handoffs', 'workbenches'] as const;

export type WorkbenchId =
  | 'valueInsights'
  | 'qualityGate'
  | 'lowValueCare'
  | 'modelGovernance'
  | 'dataSources'
  | 'countyExplorer'
  | 'rhtpReporting'
  | 'worklist'
  | 'scheduling'
  | 'reminders';

export type Access = 'full' | 'view' | 'cosign';

export interface RainSignal {
  id: string;
  title: string;
  severity: 'critical' | 'warning' | 'info';
  description: string;
  metric: string;
  sources: string[];
  chip: string;
  primary?: boolean;
}

export interface RainKpi {
  id: string;
  label: string;
  value: string;
  detail?: string;
  source: string;
  icon: string;
  tone: 'good' | 'warning' | 'critical' | 'neutral';
  chip?: string;
}

export interface RainLaunch {
  workbench: WorkbenchId;
  filter: string;
  label: string;
  detail: string;
  /** Open as soon as the turn lands (the user asked to open it). Otherwise the demo setting decides. */
  auto?: boolean;
}

export interface RainStep {
  /** The spec step this scripts (1 to 4); side turns have none. */
  step?: number;
  capability?: CapabilityId;
  /** Chip labels and typed questions that reach this step. */
  asks?: string[];
  /** One sentence in the bubble. */
  ai: string;
  /** The rest of the spec's answer, shown on the first card. */
  points?: string[];
  sources: string[];
  chips: string[];
  /** The highlighted (golden path) chip. */
  next?: string;
  viz?: string[];
  launch?: RainLaunch;
  /** A store action run when the step is entered, e.g. "approve:bp412". */
  action?: string;
}

export interface RainVizSpec {
  type: string;
  props: Record<string, unknown>;
}

export interface RainHandoff {
  id: string;
  title: string;
  count: number;
  to: string;
  workbench: WorkbenchId;
  detail: string;
}

export interface RainContract {
  signals: RainSignal[];
  kpis: RainKpi[];
  steps: Record<string, RainStep>;
  queries: string[];
  viz: Record<string, RainVizSpec>;
  handoffs: RainHandoff[];
  workbenches: Array<{ id: WorkbenchId; access: Access }>;
}

export interface WorkbenchMeta {
  id: WorkbenchId;
  nav: NavKey;
  path: string;
  title: string;
  /** P1 is opened by a guided step and fully built; P2 is representative. */
  priority: 'P1' | 'P2';
  subtitle: string;
}

/** The workbench catalog (spec), in the order the left navigation lists them. */
export const WORKBENCHES: Record<WorkbenchId, WorkbenchMeta> = {
  valueInsights: { id: 'valueInsights', nav: 'valueInsights', path: '/value-insights', title: 'Value Insights', priority: 'P1', subtitle: 'See where cost runs above expected and why. Select a part of the gap, a segment or a site to ask about it.' },
  qualityGate: { id: 'qualityGate', nav: 'qualityGate', path: '/quality-gate', title: 'Quality Gate and Campaigns', priority: 'P1', subtitle: 'Track the five gate measures, see who is behind each gap, and approve outreach campaigns.' },
  lowValueCare: { id: 'lowValueCare', nav: 'lowValueCare', path: '/low-value-care', title: 'Low-Value Care', priority: 'P2', subtitle: 'Find care that adds cost without adding value. Sort by spend, then select a measure, site or provider.' },
  modelGovernance: { id: 'modelGovernance', nav: 'modelGovernance', path: '/model-governance', title: 'Model Governance', priority: 'P1', subtitle: 'Check the risk model before outreach uses it: review the subgroup result, compare versions, then sign off.' },
  dataSources: { id: 'dataSources', nav: 'dataSources', path: '/data-sources', title: 'Data Sources', priority: 'P2', subtitle: 'Check that each feed is current before you rely on a number. Every source is labelled public or synthetic.' },
  countyExplorer: { id: 'countyExplorer', nav: 'countyExplorer', path: '/county-explorer', title: 'County Explorer', priority: 'P1', subtitle: 'Compare counties on need and access. Switch map layers and select a county for detail. All figures are aggregated and de-identified.' },
  rhtpReporting: { id: 'rhtpReporting', nav: 'rhtpReporting', path: '/rhtp-reporting', title: 'RHTP Reporting', priority: 'P2', subtitle: 'Review people served, services and outcomes by county, then export the progress report.' },
  worklist: { id: 'worklist', nav: 'worklist', path: '/worklist', title: 'Worklist', priority: 'P1', subtitle: 'Call your patients from the top down. Select a patient for their number and reasons, then book the visit or log what happened.' },
  scheduling: { id: 'scheduling', nav: 'scheduling', path: '/scheduling', title: 'Scheduling', priority: 'P1', subtitle: 'Book each waiting patient: choose a slot, check coverage, review the reminders, then confirm.' },
  reminders: { id: 'reminders', nav: 'reminders', path: '/reminders', title: 'Reminders', priority: 'P2', subtitle: 'See who has confirmed. R replies get three new slots by text; no reply by 24 hours before the visit becomes a call for Teresa.' },
};

export const workbenchByPath = (path: string) => Object.values(WORKBENCHES).find((w) => w.path === path);

/** The href a launch opens. */
export const launchHref = (l: Pick<RainLaunch, 'workbench' | 'filter'>) => `${WORKBENCHES[l.workbench].path}?filter=${encodeURIComponent(l.filter)}`;

/** Parse "approve:a,b" into its verb and arguments. */
export function parseAction(action: string): { verb: string; args: string[] } {
  const [verb, rest = ''] = action.split(':');
  return { verb, args: rest.split(',').filter(Boolean) };
}
