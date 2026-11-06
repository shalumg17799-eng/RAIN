/**
 * What each RAIN step draws: the step's `viz` ids, looked up in the same
 * persona contract and returned as contract specs. Catalog types (chart,
 * data_table, grid, stat, callout) are used as written; RAIN's own bespoke
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
import { selectionFor } from '@/components/rain/shell/store';
import { DriveScatter, ModelCard } from '@/components/rain/cards/governance';
import { PmpmTrend, QualityTracker, ScenarioPanel, SegmentPyramid, SiteCompare, Waterfall } from '@/components/rain/cards/insight';
import { AnnotatedTrend, CampaignPreview, CampaignProgress } from '@/components/rain/cards/quality';
import { BannerPreview, BriefPreview, ExportCard, HandoffCards, LaunchCard, Signoff } from '@/components/rain/cards/actions';
import { CountyMap, CountyTable, PcTrend } from '@/components/rain/cards/state';
import { TaskBriefing } from '@/components/rain/cards/care';
import KeyPointsCard from '@/components/rain/cards/KeyPointsCard';

const T = ['rain'];
const entry = (type: string, title: string, description: string, whyNotCatalog: string, component: BespokeEntry['component']) => bespoke({ type, title, description, whyNotCatalog, tenants: T, component, frame: true });

export const RAIN_CATALOG: BespokeEntry[] = [
  entry('rain.key_points', 'Key points', 'The rest of a step\'s scripted answer, above catalog visuals.', 'Closest was text; the points need the RAIN bullet style and a synthetic-data label so every screen is labelled.', KeyPointsCard),
  entry('rain.pmpm_trend', 'PMPM trend', 'Actual against expected cost per member per month since January.', 'Closest was chart (line); it starts its axis at zero, which flattens a $26 gap on $386, and it has no dashed benchmark line.', PmpmTrend),
  entry('rain.site_compare', 'Site comparison', 'One metric across the seven sites with the network reference line; bars are selectable.', 'Closest was chart (bar); it needs a fitted axis, a reference line, highlighted outliers and selection.', SiteCompare),
  entry('rain.pc_trend', 'Primary care trend', 'Primary care visits indexed to January, the two affected counties against the other four.', 'Closest was chart (line); an index from 86 to 100 needs a fitted axis, which the catalog chart does not offer.', PcTrend),
  entry('rain.waterfall', 'Gap waterfall', 'Expected to actual PMPM in four labelled parts; bars are selectable in the workbench.', 'Closest was chart (bar); a waterfall needs floating bars from a running total, which the catalog chart does not draw.', Waterfall),
  entry('rain.segment_pyramid', 'Segment pyramid', 'High-need, impactable and stable members with share of spend.', 'Closest was status_summary; a pyramid of three tiers with spend share and the action per tier has no catalog shape.', SegmentPyramid),
  entry('rain.scenario_panel', 'Scenario panel', 'Do nothing against the three moves, with the timeline to December 31.', 'Closest was chart (bar, two series); each comparison has its own unit and the timeline sits under it, which composed blocks cannot align.', ScenarioPanel),
  entry('rain.quality_tracker', 'Quality gate tracker', 'Five gate measures with current, target, status and optional projection.', 'Closest were kpi_table and target_bar; lower-is-better targets, the gate rule and projection marks on one track have no catalog type.', QualityTracker),
  entry('rain.annotated_trend', 'Annotated trend', 'Winnemucca imaging rate by month with the April rotation marked.', 'Closest was trend_chart, which draws a target line but no event marker.', AnnotatedTrend),
  entry('rain.campaign_preview', 'Campaign preview', 'The BP campaign: counts by mode, cuffs, top members and standing orders.', 'Closest was action_cards; a campaign needs counts, a member table and its approval state together.', CampaignPreview),
  entry('rain.campaign_progress', 'Campaign progress', 'Booked and controlled against the 412, live.', 'Closest was target_bar; two stacked measures on one track that move as the care team works.', CampaignProgress),
  entry('rain.launch_card', 'Launch card', 'Opens a workbench beside the conversation, pre-filtered.', 'No catalog type navigates; CatalogActions has no open-page action.', LaunchCard),
  entry('rain.handoff_cards', 'Hand-off cards', 'Hand-offs with Approve, shared across personas.', 'Closest was action_cards, which confirms one way; approval here is read by another persona\'s workbench.', HandoffCards),
  entry('rain.brief_preview', 'Brief preview', 'A board brief, provider note, governance packet, data request or state summary, with edit, approve, sign or export.', 'No catalog type previews a document with editable sections and export.', BriefPreview),
  entry('rain.banner_preview', 'Banner preview', 'How a banner will look to the care team or on every view.', 'Closest was callout; it previews another screen\'s banner in that screen\'s style.', BannerPreview),
  entry('rain.signoff', 'Sign-off', 'CIO sign-off and CMO co-sign for a model release.', 'Closest was action_cards; two signatures from two personas gate one release.', Signoff),
  entry('rain.export_card', 'Export card', 'PDF print view or CSV download of the state summary.', 'Closest was action_cards; no catalog type downloads a file or opens a print view.', ExportCard),
  entry('rain.model_card', 'Model card', 'The impactability model card with its subgroup status.', 'Closest was kpi_table; a model card pairs its fields with a pass or fail subgroup status that changes after sign-off.', ModelCard),
  entry('rain.drive_scatter', 'Drive-time scatter', 'Drive time against primary care visits, frontier vs town.', 'The catalog chart draws line and bar only, not scatter.', DriveScatter),
  entry('rain.county_map', 'County map', 'Nevada county choropleth with layer toggles, frontier places and targeting.', 'Closest was chart; the catalog has no map, and a county choropleth with layer toggles, frontier places and selection needs one.', CountyMap),
  entry('rain.county_table', 'County table', 'Six counties side by side with heat and suppressed cells.', 'Closest was data_table; heat colouring and suppression marks per cell.', CountyTable),
  entry('rain.task_briefing', 'Task briefing', 'Today\'s queue for the care team with the button into the main workbench.', 'No catalog type for a task queue that opens a workbench.', TaskBriefing),
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
