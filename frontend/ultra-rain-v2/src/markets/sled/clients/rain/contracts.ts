/**
 * Contracts of the `rain.*` bespoke (tier 4) component types: identity,
 * version, the props each takes, the defaults the component applies, its
 * variants and where the implementation lives (core/catalog/contracts.ts).
 *
 * First drafted from the recorded answers by `npm run contracts:infer`, then
 * owned here: when a component's props change, change its schema in the same
 * commit. `core/catalog/contracts.test.ts` fails if a recorded answer stops
 * matching, a binding points at another component, or a type is missing.
 * Objects are open (extra fields pass); a field is optional when a recorded
 * answer omits it or the component defaults it. A state field uses the
 * standard status vocabulary where its values are those words, else the enum
 * of the domain values the component draws; free text stays a string.
 */
import { z } from 'zod';
import { defineContracts } from '@core/catalog/contracts';

export default defineContracts([
  {
    type: 'rain.brief_preview',
    version: 1,
    title: 'Brief preview',
    description: 'A board brief, provider note, governance packet, data request or state summary, with edit, approve, sign or export.',
    whyNotCatalog: 'Kept custom: an editable draft with approve-and-send, sign-off and export, all written to the demo store.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/actions#BriefPreview',
    example: { persona: 'rain_cio', flowKey: 'cio_adt' },
    defaults: {editable: false},
    schema: z.object({
      kind: z.string(),
      points: z.array(z.string()).optional(),
      editable: z.boolean().optional(),
    }),
  },
  {
    type: 'rain.campaign_preview',
    version: 1,
    title: 'Campaign preview',
    description: 'The BP campaign ready to approve: member counts by visit mode, cuffs to ship, the top five members and its approval state.',
    whyNotCatalog: 'Kept custom: its approval pill reads the live store and turns to "Sent to the Worklist" once the hand-off is approved, which a shared block would freeze at answer time.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/quality#CampaignPreview',
    example: { persona: 'rain_cmo', flowKey: 'cmo_campaign' },
    schema: z.object({
      points: z.array(z.string()),
    }),
  },
  {
    type: 'rain.campaign_progress',
    version: 1,
    title: 'Campaign progress',
    description: 'Booked and controlled against the 412, live.',
    whyNotCatalog: 'Kept custom: the booked and controlled counts are read live from the store and move as the care team works.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/quality#CampaignProgress',
    example: { persona: 'rain_chw', flowKey: 'chw_progress' },
    defaults: {compact: false},
    variants: [
      { name: 'default', description: 'Drawn when no variant prop is set.' },
      { name: 'compact', description: 'Drawn with `compact: true`.', when: {compact: true} },
    ],
    schema: z.object({
      compact: z.boolean().optional(),
    }),
  },
  {
    type: 'rain.county_map',
    version: 1,
    title: 'County map',
    description: 'Nevada county choropleth with layer toggles, frontier places and targeting.',
    whyNotCatalog: 'Kept custom: an SVG county map with a layer toggle, frontier places and selection; the catalog has no map.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/state#CountyMap',
    example: { persona: 'rain_state', flowKey: 'st_funds' },
    defaults: {mode: "ed"},
    variants: [
      { name: 'broadband', description: 'Drawn with `mode: \'broadband\'`.', when: {mode: "broadband"} },
      { name: 'ed', description: 'Drawn with `mode: \'ed\'` (the default).' },
      { name: 'frontier', description: 'Drawn with `mode: \'frontier\'`.', when: {mode: "frontier"} },
      { name: 'layers', description: 'Drawn with `mode: \'layers\'`.', when: {mode: "layers"} },
      { name: 'target', description: 'Drawn with `mode: \'target\'`.', when: {mode: "target"} },
    ],
    schema: z.object({
      mode: z.enum(['broadband', 'ed', 'frontier', 'layers', 'target']).optional(),
      points: z.array(z.string()).optional(),
    }),
  },
  {
    type: 'rain.county_table',
    version: 1,
    title: 'County table',
    description: 'Six counties side by side with heat and suppressed cells.',
    whyNotCatalog: 'Kept custom: the heat-coloured cells, HPSA pills and suppressed-cell marks must survive the narrow Ask AI pane, where the catalog table\'s stacked cards draw plain text.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/state#CountyTable',
    example: { persona: 'rain_state', flowKey: 'st_county' },
    schema: z.object({
      points: z.array(z.string()),
    }),
  },
  {
    type: 'rain.drive_scatter',
    version: 1,
    title: 'Drive-time scatter',
    description: 'Drive time against primary care visits, frontier vs town.',
    whyNotCatalog: 'Kept custom: a scatter on two numeric axes, which the catalog chart (line and bar only) does not draw.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/governance#DriveScatter',
    example: { persona: 'rain_cio', flowKey: 'cio_subgroup' },
    schema: z.object({}),
  },
  {
    type: 'rain.export_card',
    version: 1,
    title: 'Export card',
    description: 'PDF print view or CSV download of the state summary.',
    whyNotCatalog: 'Kept custom: it builds a CSV download or opens the print view, which no catalog type does.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/actions#ExportCard',
    example: { persona: 'rain_state', flowKey: 'st_pdf' },
    schema: z.object({
      format: z.string(),
    }),
  },
  {
    type: 'rain.handoff_cards',
    version: 1,
    title: 'Hand-off cards',
    description: 'Hand-offs with Approve, shared across personas.',
    whyNotCatalog: 'Kept custom: Approve writes the shared store that another persona\'s workbench reads, which action_cards cannot reproduce.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/actions#HandoffCards',
    example: { persona: 'rain_cmo', flowKey: 'cmo_approve' },
    schema: z.object({
      ids: z.array(z.string()),
    }),
  },
  {
    type: 'rain.key_points',
    version: 1,
    title: 'Key points',
    description: 'The rest of a step\'s scripted answer, above catalog visuals.',
    whyNotCatalog: 'Kept custom: the points share the bullet style of the points inside every RAIN card, so a step reads the same whichever card comes first.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/KeyPointsCard',
    example: { persona: 'rain_cio', flowKey: 'cio_fix' },
    schema: z.object({
      points: z.array(z.string()),
    }),
  },
  {
    type: 'rain.launch_card',
    version: 1,
    title: 'Launch card',
    description: 'Opens a workbench beside the conversation, pre-filtered.',
    whyNotCatalog: 'Kept custom: it hides its Open button when that workbench is already on screen and changes its line inside the Ask AI pane, which a callout link cannot do.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/actions#LaunchCard',
    example: { persona: 'rain_chw', flowKey: 'chw_open' },
    schema: z.object({
      step: z.string(),
    }),
  },
  {
    type: 'rain.model_card',
    version: 1,
    title: 'Model card',
    description: 'The impactability model card with its subgroup status.',
    whyNotCatalog: 'Kept custom: its version, subgroup status and fix preview read the live sign-off and preview state, which a shared block would freeze at answer time.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/governance#ModelCard',
    example: { persona: 'rain_cio', flowKey: 'cio_card' },
    schema: z.object({
      points: z.array(z.string()).optional(),
    }),
  },
  {
    type: 'rain.scenario_panel',
    version: 1,
    title: 'Scenario panel',
    description: 'Do nothing against the three moves, with the timeline to December 31.',
    whyNotCatalog: 'Kept custom: three paired meters with their own units sit over a four-step timeline in a container-aware grid; the shared grid would squeeze them into three columns in the narrow Ask AI pane.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/insight#ScenarioPanel',
    example: { persona: 'rain_ceo', flowKey: 'ceo_nothing' },
    schema: z.object({
      points: z.array(z.string()).optional(),
      focus: z.string().optional(),
    }),
  },
  {
    type: 'rain.segment_pyramid',
    version: 1,
    title: 'Segment pyramid',
    description: 'High-need, impactable and stable members with share of spend.',
    whyNotCatalog: 'Kept custom: the three tiers are drawn as a pyramid whose widths show their size; as a table the shape the answer relies on is lost.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/insight#SegmentPyramid',
    example: { persona: 'rain_ceo', flowKey: 'ceo_gap' },
    schema: z.object({
      focus: z.string().optional(),
      points: z.array(z.string()).optional(),
    }),
  },
  {
    type: 'rain.signoff',
    version: 1,
    title: 'Sign-off',
    description: 'CIO sign-off and CMO co-sign for a model release.',
    whyNotCatalog: 'Kept custom: a two-signature release flow across two personas, kept in the demo store.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/actions#Signoff',
    example: { persona: 'rain_cio', flowKey: 'cio_signoff' },
    schema: z.object({}),
  },
  {
    type: 'rain.site_compare',
    version: 1,
    title: 'Site comparison',
    description: 'One metric across the seven sites with the network reference line; bars are selectable.',
    whyNotCatalog: 'Kept custom: the catalog chart cannot print the $ on its axis or shorten the seven site names, which keeps the bars readable in the narrow pane.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/insight#SiteCompare',
    example: { persona: 'rain_ceo', flowKey: 'ceo_sites' },
    defaults: {metric: "pmpm"},
    schema: z.object({
      metric: z.string().optional(),
    }),
  },
  {
    type: 'rain.task_briefing',
    version: 1,
    title: 'Task briefing',
    description: 'Today\'s queue for the care team with the button into the main workbench.',
    whyNotCatalog: 'Kept custom: it adds a cross-persona hand-off line once approved, carries the live campaign progress and deep-links into the workbench.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/care#TaskBriefing',
    example: { persona: 'rain_chw', flowKey: 'chw_brief' },
    schema: z.object({
      role: z.string(),
    }),
  },
  {
    type: 'rain.waterfall',
    version: 1,
    title: 'Gap waterfall',
    description: 'Expected to actual PMPM in four labelled parts; bars are selectable in the workbench.',
    whyNotCatalog: 'Kept custom: floating bars from a running total, selectable on the workbench, which the catalog chart does not draw.',
    tenants: ['rain'],
    implementation: '@/components/value-based-care/cards/insight#Waterfall',
    example: { persona: 'rain_ceo', flowKey: 'ceo_gap' },
    schema: z.object({
      points: z.array(z.string()),
    }),
  },
]);
