/**
 * What each RAIN step draws: the step's `viz` ids, looked up in the same
 * persona contract and returned as contract specs. Catalog types (chart,
 * data_table, grid, stack, stat, callout) are used as written; RAIN's own bespoke
 * types draw the shapes the catalog cannot. The step's `points` go to its
 * first card.
 */
import { bespoke, spec } from '@core/catalog/bespoke';
import type { BespokeEntry } from '@core/catalog/bespoke';
import type { ContractSpec } from '@core/contract/spec';
import type { RainContract, RainVizSpec } from '@/data/rain/_shared/contract';
import { DATASETS } from '@/data/rain/_shared/datasets';
import type { ContextKind } from '@/data/rain/_shared/context';
import { contextSpecs } from '@/data/rain/_shared/context';
import { selectionFor } from '@/components/value-based-care/shell/store';
import { DriveScatter, ModelCard } from '@/components/value-based-care/cards/governance';
import { ScenarioPanel, SegmentPyramid, SiteCompare, Waterfall } from '@/components/value-based-care/cards/insight';
import { CampaignPreview, CampaignProgress } from '@/components/value-based-care/cards/quality';
import { BriefPreview, ExportCard, HandoffCards, LaunchCard, Signoff } from '@/components/value-based-care/cards/actions';
import { CountyMap, CountyTable } from '@/components/value-based-care/cards/state';
import { TaskBriefing } from '@/components/value-based-care/cards/care';
import KeyPointsCard from '@/components/value-based-care/cards/KeyPointsCard';

// Each type's title, description and why no catalog type fits are its
// contract's (./contracts.ts); a binding names only the component.
const entry = (type: string, component: BespokeEntry['component']) => bespoke({ type, component, frame: true });

export const RAIN_CATALOG: BespokeEntry[] = [
  entry('rain.key_points', KeyPointsCard),
  entry('rain.site_compare', SiteCompare),
  entry('rain.waterfall', Waterfall),
  entry('rain.segment_pyramid', SegmentPyramid),
  entry('rain.scenario_panel', ScenarioPanel),
  entry('rain.campaign_preview', CampaignPreview),
  entry('rain.campaign_progress', CampaignProgress),
  entry('rain.launch_card', LaunchCard),
  entry('rain.handoff_cards', HandoffCards),
  entry('rain.brief_preview', BriefPreview),
  entry('rain.signoff', Signoff),
  entry('rain.export_card', ExportCard),
  entry('rain.model_card', ModelCard),
  entry('rain.drive_scatter', DriveScatter),
  entry('rain.county_map', CountyMap),
  entry('rain.county_table', CountyTable),
  entry('rain.task_briefing', TaskBriefing),
];

const NOTE = 'Synthetic data for a demo; every person and organization is fictional.';

/**
 * Contract viz → spec. A `dataset` prop names a dataset (resolved from
 * `_shared/datasets.ts`, the API seam); nested children are wrapped so every
 * node carries its version.
 */
function toSpec(v: RainVizSpec): ContractSpec {
  const { dataset, ...rest } = v.props as Record<string, unknown> & { dataset?: string };
  const props = { ...(dataset ? DATASETS[dataset]() : {}), ...rest } as Record<string, unknown>;
  if (Array.isArray(props.children)) props.children = (props.children as Array<RainVizSpec | ContractSpec>).map((c) => ('version' in c ? c : toSpec(c as RainVizSpec)));
  return spec(v.type, props);
}

/**
 * A table's caption becomes a visible title above it: the catalog table keeps
 * its caption screen-reader only, which would leave an answer's table untitled.
 */
function titled(sp: ContractSpec): ContractSpec {
  const props = sp.props as Record<string, unknown>;
  if (sp.type === 'data_table' && typeof props.caption === 'string') {
    const { caption, ...rest } = props;
    return spec('stack', { children: [spec('text', { text: caption, size: 'sm', tone: 'muted' }), spec('data_table', { ...rest, stack: true })] });
  }
  if (Array.isArray(props.children)) return { ...sp, props: { ...props, children: (props.children as ContractSpec[]).map(titled) } };
  return sp;
}

/** The components for one step; `messageId` keeps a context answer on the selection it was asked about. */
export function rainAnswers(contract: RainContract, flowKey: string | undefined, messageId?: string | number): ContractSpec[] | undefined {
  if (!flowKey) return undefined;
  const step = contract.steps[flowKey];
  if (!step?.viz?.length) return undefined;
  // State lead: each county context step says which county it is about.
  const county = flowKey.startsWith('st_ctx_') ? flowKey.slice('st_ctx_'.length) : undefined;
  const specs = step.viz
    .map((id) => contract.viz[id])
    .filter(Boolean)
    .flatMap((v) => (v.type === 'context' ? contextSpecs(v.props.kind as ContextKind, selectionFor(messageId).id, county) : [toSpec(v)]))
    .map(titled);
  // Catalog visuals carry no label of their own: the answer says the data is synthetic (spec: "label synthetic data on every screen").
  if (specs.some((s) => !s.type.startsWith('rain.'))) specs.push(spec('illustrative_note', { note: NOTE }));
  if (step.points?.length) {
    const first = specs[0];
    if (first && first.type.startsWith('rain.') && first.type !== 'rain.launch_card') first.props = { ...first.props, points: step.points };
    else specs.unshift(spec('rain.key_points', { points: step.points }));
  }
  return specs;
}
