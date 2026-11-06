/**
 * Export the component catalog for the backend: `npm run catalog`.
 *
 * Writes docs/catalog/catalog.json — every component type with its version,
 * tier, description (what the LLM reads), JSON Schema for its props, an
 * example payload, its loading/empty/error states and the clients whose
 * answers draw it — plus every bespoke (tier 4) type with the props shape
 * observed in the recorded answers, and the AiTurn and signal schemas. This is
 * the payload `GET /catalog` serves; generating it from the registry and the
 * recorded answers is what keeps the API and the UI from drifting.
 *
 * Also writes docs/catalog/reuse.md (the contract plan's reuse number: the
 * share of answer components served by catalog types, per persona) and
 * docs/catalog/inventory.md (every tenant component grouped into shapes) and
 * docs/catalog/personas.json (every client/persona, for `npm run visual`).
 *
 *   npm run catalog            write the file
 *   npm run catalog -- --check exit 1 if the committed file is out of date
 */
import { writeFileSync, readFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { z } from 'zod';
import { CATALOG } from '../src/core/catalog/registry';
import { aiTurnSchema } from '../src/core/contract/aiTurn';
import { signalSchema } from '../src/core/contract/signal';
import { STATUSES } from '../src/core/contract/status';
import { ICONS } from '../src/core/contract/icons';
import { ICON_TONES } from '../src/core/contract/tone';
import { getMarkets } from '../src/core/runtime/registry';
import { contractComponents, type ContractSpec } from '../src/core/contract/spec';
import { readdirSync, statSync } from 'node:fs';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(APP, 'docs/catalog/catalog.json');
const REUSE = join(APP, 'docs/catalog/reuse.md');
const INVENTORY = join(APP, 'docs/catalog/inventory.md');
const PERSONAS = join(APP, 'docs/catalog/personas.json');

const json = (schema: z.ZodType) => z.toJSONSchema(schema, { unrepresentable: 'any', io: 'input' });

// ── Usage: every recorded answer of every persona ───────────────────
type Shape = { type: string; props?: Record<string, Shape>; items?: Shape; optional?: boolean };
/** A JSON-Schema-like shape inferred from observed values (merged across examples). */
function infer(v: unknown, depth = 0): Shape {
  if (Array.isArray(v)) return { type: 'array', items: depth > 3 || !v.length ? { type: 'any' } : v.slice(0, 5).map((x) => infer(x, depth + 1)).reduce(merge) };
  if (v && typeof v === 'object') {
    if (depth > 3) return { type: 'object' };
    return { type: 'object', props: Object.fromEntries(Object.entries(v).filter(([, x]) => x !== undefined).map(([k, x]) => [k, infer(x, depth + 1)])) };
  }
  return { type: v === null ? 'null' : typeof v };
}
function merge(a: Shape, b: Shape): Shape {
  if (a.type !== b.type) return { type: [...new Set([...a.type.split('|'), ...b.type.split('|')])].sort().join('|') };
  if (a.type === 'object' && (a.props || b.props)) {
    const keys = new Set([...Object.keys(a.props ?? {}), ...Object.keys(b.props ?? {})]);
    return { type: 'object', props: Object.fromEntries([...keys].map((k) => {
      const x = a.props?.[k]; const y = b.props?.[k];
      return [k, x && y ? merge(x, y) : { ...(x ?? y)!, optional: true }];
    })) };
  }
  if (a.type === 'array' && a.items && b.items) return { type: 'array', items: merge(a.items, b.items) };
  return a;
}
function toJsonSchema(sh: Shape): Record<string, unknown> {
  if (sh.type === 'object' && sh.props) {
    const req = Object.entries(sh.props).filter(([, x]) => !x.optional).map(([k]) => k);
    return { type: 'object', properties: Object.fromEntries(Object.entries(sh.props).map(([k, x]) => [k, toJsonSchema(x)])), ...(req.length ? { required: req } : {}) };
  }
  if (sh.type === 'array') return { type: 'array', ...(sh.items && sh.items.type !== 'any' ? { items: toJsonSchema(sh.items) } : {}) };
  if (sh.type.includes('|')) return { type: sh.type.split('|') };
  return sh.type === 'any' ? {} : { type: sh.type };
}
const flatten = (specs: ContractSpec[]): ContractSpec[] => specs.flatMap((sp) => {
  const kids = Array.isArray(sp.props?.children) ? (sp.props.children as unknown[]).filter((c): c is ContractSpec => !!c && typeof c === 'object' && 'type' in (c as object)) : [];
  return [sp, ...flatten(kids)];
});
const catalogTypes = new Set(CATALOG.map((e) => e.type));
const used = new Map<string, Set<string>>();
const bespoke = new Map<string, { title: string; description: string; whyNotCatalog?: string; tenants: Set<string>; shape?: Shape; turns: number }>();
const personaRows: Array<{ client: string; persona: string; turns: number; answered: number; catalog: number; bespoke: number }> = [];
for (const market of getMarkets()) for (const client of market.clients) for (const persona of client.personas) {
  const m = (await persona.load()).default;
  const own = new Map((m.catalog ?? []).map((e) => [e.type, e]));
  const row = { client: client.id, persona: persona.id, turns: 0, answered: 0, catalog: 0, bespoke: 0 };
  for (const [flowKey, flow] of Object.entries(m.flows.chatFlows)) {
    row.turns += 1;
    const ui = (flow as { ui_components_to_render?: unknown[] }).ui_components_to_render ?? [];
    const specs = flatten([...contractComponents(ui), ...(m.answers?.({ flowKey, role: 'ai', uiComponents: ui }, m.signals ?? []) ?? [])]);
    if (specs.length) row.answered += 1;
    for (const sp of specs) {
      if (!used.has(sp.type)) used.set(sp.type, new Set());
      used.get(sp.type)!.add(client.id);
      if (catalogTypes.has(sp.type)) { row.catalog += 1; continue; }
      row.bespoke += 1;
      const e = own.get(sp.type);
      const b = bespoke.get(sp.type) ?? { title: e?.title ?? sp.type, description: e?.description ?? '', whyNotCatalog: e?.whyNotCatalog, tenants: new Set<string>(), turns: 0 };
      b.tenants.add(client.id); b.turns += 1;
      const { children: _children, ...props } = sp.props ?? {};
      const sh = infer(props);
      b.shape = b.shape ? merge(b.shape, sh) : sh;
      bespoke.set(sp.type, b);
    }
  }
  for (const e of m.catalog ?? []) if (!bespoke.has(e.type)) bespoke.set(e.type, { title: e.title, description: e.description, whyNotCatalog: e.whyNotCatalog, tenants: new Set(e.tenants), turns: 0 });
  personaRows.push(row);
}

/** Loading, empty and error behaviour: the renderer's, plus what an empty list does. */
function states(schema: Record<string, unknown>) {
  const props = (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = new Set((schema.required ?? []) as string[]);
  const minList = Object.entries(props).find(([k, v]) => required.has(k) && v.type === 'array' && typeof v.minItems === 'number');
  return {
    loading: 'A skeleton placeholder while the component\'s code loads (first use only).',
    empty: minList
      ? `An empty \`${minList[0]}\` fails validation and shows the invalid-data notice: omit the component when there is nothing to show.`
      : 'Draws with the fields present; optional fields are simply left out.',
    invalid: 'Props that do not match the schema draw a small notice instead of the card; the rest of the answer is unaffected.',
    error: 'A render failure draws a "couldn\'t be rendered" notice inside an error boundary; the thread is unaffected.',
  };
}

const catalog = {
  $comment: 'Generated by `npm run catalog` from src/core/catalog/registry.ts — do not edit by hand.',
  contractVersion: 1,
  response: { name: 'AiTurn', schema: json(aiTurnSchema) },
  vocabularies: {
    status: STATUSES,
    icons: Object.keys(ICONS),
    iconTones: ICON_TONES,
    signal: json(signalSchema),
  },
  components: CATALOG.map((e) => ({
    type: e.type,
    version: e.version,
    tier: e.tier,
    title: e.title,
    description: e.description,
    props: json(e.schema),
    example: e.example,
    states: states(json(e.schema) as Record<string, unknown>),
    tenants: [...(used.get(e.type) ?? [])].sort(),
  })),
  bespoke: [...bespoke.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([type, b]) => ({
    type,
    version: 1,
    tier: 4,
    title: b.title,
    description: b.description,
    ...(b.whyNotCatalog ? { whyNotCatalog: b.whyNotCatalog } : {}),
    tenants: [...b.tenants].sort(),
    props: b.shape ? toJsonSchema(b.shape) : { type: 'object' },
  })),
};

// ── Reuse report (the contract plan's "are we still rebuilding?" number) ──
const total = personaRows.reduce((a, r) => ({ c: a.c + r.catalog, b: a.b + r.bespoke }), { c: 0, b: 0 });
const pct = (c: number, b: number) => (c + b ? `${Math.round((100 * c) / (c + b))}%` : '—');
const byClient = new Map<string, { c: number; b: number; p: number }>();
for (const r of personaRows) { const x = byClient.get(r.client) ?? { c: 0, b: 0, p: 0 }; x.c += r.catalog; x.b += r.bespoke; x.p += 1; byClient.set(r.client, x); }
const reuse = [
  '<!-- Generated by `npm run catalog` — do not edit by hand. -->',
  '# Reuse report',
  '',
  'Every answer component of every scripted turn, counted by where it comes from: the catalog (tiers 2–3, steps 1–3 of the gap ladder: pick, extend, compose) or a tenant\'s bespoke type (tier 4, step 4: create). The number to watch is the catalog share; each bespoke type is a candidate to promote or retire.',
  '',
  `**Catalog share of answer components: ${pct(total.c, total.b)}** (${total.c} catalog, ${total.b} bespoke) across ${personaRows.length} personas. Catalog types: ${CATALOG.length} (tier 2: ${CATALOG.filter((e) => e.tier === 2).length}, tier 3: ${CATALOG.filter((e) => e.tier === 3).length}). Bespoke types: ${bespoke.size}.`,
  '',
  '## By client',
  '',
  '| Client | Personas | Catalog | Bespoke | Catalog share |',
  '|---|---:|---:|---:|---:|',
  ...[...byClient.entries()].map(([c, x]) => `| ${c} | ${x.p} | ${x.c} | ${x.b} | ${pct(x.c, x.b)} |`),
  '',
  '## By persona',
  '',
  '| Client | Persona | Turns | Turns with components | Catalog | Bespoke | Catalog share |',
  '|---|---|---:|---:|---:|---:|---:|',
  ...personaRows.map((r) => `| ${r.client} | ${r.persona} | ${r.turns} | ${r.answered} | ${r.catalog} | ${r.bespoke} | ${pct(r.catalog, r.bespoke)} |`),
  '',
  '## Catalog types in use',
  '',
  '| Type | Tier | Clients |',
  '|---|---:|---|',
  ...CATALOG.map((e) => `| \`${e.type}\` | ${e.tier} | ${[...(used.get(e.type) ?? [])].sort().join(', ') || '— (available, not yet drawn)'} |`),
  '',
].join('\n');

// ── Component inventory: tenant components grouped into shapes ─────────
// Tenant component folders: the one list lint and the audit read (tenants.config.json).
const TENANT_DIRS = (JSON.parse(readFileSync(join(APP, 'tenants.config.json'), 'utf8')).tenantFolders as string[])
  .filter((t) => existsSync(join(APP, 'src/components', t)));
const SHAPES: Array<[string, RegExp, string]> = [
  ['Table / ranked list', /(Table|Rollup|Leaderboard|Ranking|Matrix|Grid)$/, 'kpi_table, data_table'],
  ['Chart (trend, bar, waterfall)', /(Chart|Trend|TrendLine|Bar|Bars|Waterfall|Histogram|Sparkline|Curve|Forecast|Funnel)$/, 'trend_chart, chart, peer_bar, target_bar'],
  ['Gauge / score', /(Gauge|Ring|Dial|Score|Meter)$/, 'gauge'],
  ['KPI tiles / strip', /(Kpi|KPI|Stats?|Tiles?|Carousel|Strip|Row|Bars?Strip)$/, 'stat_tiles, metric_card, hero_metric'],
  ['Signal / insight card', /(Signals?|Insight|Alert|AlertBand|Callout|Spike)$/, 'signal_card, signal_tile, callout'],
  ['Action / approval card', /(Action|Actions|Approval|Board|Composer|Notice|Draft|Receipt|Confirm)$/, 'action_cards'],
  ['Timeline / calendar / roadmap', /(Timeline|Calendar|Roadmap|Schedule|Log|Trail|Feed|History)$/, 'data_table, stack'],
  ['Lineage / trace / process', /(Lineage|Trace|Flow|Diagram|Journey|Path|Map)$/, 'current_state_diagram, journey_map'],
  ['Panel / card (composed)', /(Panel|Card|View|Section|Summary|Brief|Briefing|Preview|Detail)$/, 'stack, grid of catalog types'],
  ['Modal / drawer / overlay', /(Modal|Drawer|Overlay|Sheet|Dialog|Popover)$/, '— shell (tier 1)'],
  ['Deck slide / presentation', /(Slide|Deck|Presentation|Chrome|Footer|Header)$/, '— shell (tier 1)'],
];
const files: Array<{ tenant: string; name: string }> = [];
for (const t of TENANT_DIRS) {
  const walk = (d: string) => { for (const n of readdirSync(d)) { const p = join(d, n); if (statSync(p).isDirectory()) walk(p); else if (/\.(jsx|tsx)$/.test(n) && !/\.test\./.test(n)) files.push({ tenant: t, name: n.replace(/\.(jsx|tsx)$/, '') }); } };
  walk(join(APP, 'src/components', t));
}
const groups = new Map<string, { tenants: Set<string>; names: string[]; maps: string }>();
for (const f of files) {
  const hit = SHAPES.find(([, re]) => re.test(f.name));
  const key = hit ? hit[0] : 'Other (state, helpers, one-offs)';
  const g = groups.get(key) ?? { tenants: new Set<string>(), names: [], maps: hit ? hit[2] : '—' };
  g.tenants.add(f.tenant); g.names.push(f.name); groups.set(key, g);
}
const inventory = [
  '<!-- Generated by `npm run catalog` — do not edit by hand. -->',
  '# Component inventory',
  '',
  `${files.length} component files in tenant folders, grouped into shapes by what they are. The right-hand column is the catalog type a new answer of that shape should use (the gap ladder: pick, extend, compose, then create). Existing bespoke components stay drawable as tier-4 types until each is promoted into one of these or retired.`,
  '',
  '| Shape | Files | Clients | Catalog type to use | Examples |',
  '|---|---:|---|---|---|',
  ...[...groups.entries()].sort((a, b) => b[1].names.length - a[1].names.length).map(([k, g]) => `| ${k} | ${g.names.length} | ${[...g.tenants].sort().join(', ')} | ${g.maps} | ${g.names.slice(0, 4).join(', ')} |`),
  '',
].join('\n');

const personaList = personaRows.map((r) => ({ client: r.client, persona: r.persona }));
const outputs: Array<[string, string]> = [[OUT, `${JSON.stringify(catalog, null, 2)}\n`], [REUSE, reuse], [INVENTORY, inventory], [PERSONAS, `${JSON.stringify(personaList, null, 2)}\n`]];
if (process.argv.includes('--check')) {
  const stale = outputs.filter(([f, t]) => (existsSync(f) ? readFileSync(f, 'utf8') : '') !== t);
  if (stale.length) {
    console.error(`${stale.map(([f]) => f.replace(`${APP}/`, '')).join(', ')} out of date — run \`npm run catalog\`.`);
    process.exit(1);
  }
  console.log('catalog.json, reuse.md, inventory.md and personas.json are up to date.');
} else {
  mkdirSync(dirname(OUT), { recursive: true });
  for (const [f, t] of outputs) writeFileSync(f, t);
  console.log(`Wrote ${CATALOG.length} catalog types and ${bespoke.size} bespoke types to docs/catalog/catalog.json; reuse ${pct(total.c, total.b)}.`);
}
process.exit(0);
