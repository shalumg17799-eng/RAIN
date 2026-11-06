/**
 * Named datasets the persona contracts reference by id (spec: "steps
 * reference data by ID only"). Each returns the props of a catalog component
 * (chart, data_table, grid), built from the master numbers and records, so a
 * backend swaps this module for GET /datasets/:id with no change to a
 * contract or a component.
 */
import type { ContractSpec } from '@core/contract/spec';
import { spec } from '@core/catalog/bespoke';
import { BP, COUNTIES, LV_MEASURES, MEASURES, MODEL, OPTIONS, SITES, STATE, num, usdK, usdM } from './constants';
import { FEATURES, SUBGROUP, getCampaignMembers, getReminders, getSwaps, getTeresaWorklist } from './records';

type Props = Record<string, unknown>;

const SOCIAL: Record<string, number> = { elko: 44, wells: 31, winnemucca: 35, battleMountain: 29, lovelock: 33, ely: 41, fallon: 42 };

const memberTable = (rows: ReturnType<typeof getCampaignMembers>, caption: string): Props => ({
  caption,
  columns: [
    { key: 'rank', label: '#', kind: 'number' },
    { key: 'name', label: 'Member' },
    { key: 'reasons', label: 'Top reasons' },
    { key: 'likely', label: 'Likely to control', align: 'right' },
    { key: 'mode', label: 'Visit mode' },
  ],
  rows: rows.map((m) => ({ rank: m.rank, name: m.name, reasons: m.reasons.join(' · '), likely: `${m.likelihood}%`, mode: m.mode })),
});

const stat = (label: string, value: string, caption?: string, status?: string): ContractSpec => spec('stat', { label, value, ...(caption ? { caption } : {}), ...(status ? { status } : {}) });

const reminderTable = (filter: 'unconfirmed' | 'r'): Props => {
  const rows = getReminders().filter((r) => (filter === 'r' ? r.status === 'Change requested (R)' : r.status === 'No reply yet'));
  return {
    caption: filter === 'r' ? `${rows.length} patients replied R` : `${rows.length} visits tomorrow with no reply`,
    columns: [
      { key: 'name', label: 'Patient' },
      { key: 'visit', label: 'Visit' },
      { key: 'language', label: 'Language' },
      { key: 'next', label: 'Next step' },
    ],
    rows: rows.map((r) => ({ name: r.name, visit: r.visit, language: r.language, next: filter === 'r' ? 'Three new slots by SMS' : 'Call task on Teresa’s worklist' })),
  };
};

export const DATASETS: Record<string, () => Props> = {
  site_imaging: () => ({ kind: 'bar', unit: '%', title: 'Low back pain imaging by site, share of eligible visits (network 9%)', series: [{ name: 'Imaging rate', points: SITES.map((s) => ({ label: s.name, value: s.imagingPct })) }] }),
  site_lowvalue: () => ({ kind: 'bar', title: 'Low-value spend by site, $K a year', series: [{ name: 'Low-value care ($K)', points: SITES.map((s) => ({ label: s.name, value: s.lowValue / 1000 })) }] }),
  site_social: () => ({ kind: 'bar', unit: '%', title: 'Members with a social needs screening, by site (network 38%)', series: [{ name: 'Screened', points: SITES.map((s) => ({ label: s.name, value: SOCIAL[s.id] })) }] }),
  lv_top5: () => ({
    caption: `The five largest of ${LV_MEASURES.length} low-value measures (${num(2140)} services, ${usdK(618_000)} a year in all)`,
    columns: [
      { key: 'measure', label: 'Measure' },
      { key: 'basis', label: 'Basis' },
      { key: 'services', label: 'Services', kind: 'number' },
      { key: 'spend', label: 'Annual spend', align: 'right' },
    ],
    rows: [...LV_MEASURES].sort((a, b) => b.dollars - a.dollars).slice(0, 5).map((m) => ({ measure: m.name, basis: m.basis, services: m.services, spend: usdK(m.dollars) })),
  }),
  projection_2027: () => ({
    kind: 'line',
    unit: '%',
    title: 'Gap to expected cost by quarter, through 2027',
    series: [
      { name: 'Do nothing', points: [6.7, 6.9, 7.1, 7.2, 7.4].map((v, i) => ({ label: ['Q4 2026', 'Q1 2027', 'Q2 2027', 'Q3 2027', 'Q4 2027'][i], value: v })) },
      { name: 'Three moves', points: [3.5, 3.0, 2.4, 1.8, 1.2].map((v, i) => ({ label: ['Q4 2026', 'Q1 2027', 'Q2 2027', 'Q3 2027', 'Q4 2027'][i], value: v })) },
    ],
  }),
  measure_projection: () => ({
    kind: 'bar',
    unit: '%',
    title: 'Each gate measure: current, projected by December 31, and target (CMS122 is lower-is-better)',
    series: [
      { name: 'Current', points: MEASURES.map((m) => ({ label: m.id, value: m.current })) },
      { name: 'Projected Dec 31', points: MEASURES.map((m) => ({ label: m.id, value: m.projected })) },
      { name: 'Target', points: MEASURES.map((m) => ({ label: m.id, value: m.target })) },
    ],
  }),
  mode_split: () => ({
    columns: 3,
    children: [
      stat('Telehealth with home cuff', num(BP.telehealth), 'Drive more than an hour', 'info'),
      stat('In person', num(BP.inPerson), 'Drive under an hour'),
      stat('Cuffs to ship first', num(BP.cuffsToShip), 'Before the telehealth visit', 'warning'),
    ],
  }),
  campaign_top10: () => memberTable(getCampaignMembers().slice(0, 10), `Top 10 of the ${BP.nearControl}, by likelihood of reaching control`),
  teresa_top5: () => memberTable(getTeresaWorklist().slice(0, 5), 'Your five patients closest to control'),
  teresa_noreply: () => ({
    caption: 'Called yesterday, no callback yet: call these back today',
    columns: [
      { key: 'rank', label: '#', kind: 'number' },
      { key: 'name', label: 'Patient' },
      { key: 'phone', label: 'Phone' },
      { key: 'best', label: 'Best time' },
      { key: 'mode', label: 'Visit mode' },
    ],
    rows: getTeresaWorklist()
      .filter((m) => m.status === 'Left message')
      .map((m) => ({ rank: m.rank, name: m.name, phone: m.phone, best: m.bestTime, mode: m.mode })),
  }),
  subgroup: () => ({
    kind: 'bar',
    title: 'Average risk rank by condition group (percentile), frontier vs town',
    series: [
      { name: 'Town', points: SUBGROUP.map((g) => ({ label: g.group, value: g.town })) },
      { name: 'Frontier', points: SUBGROUP.map((g) => ({ label: g.group, value: g.frontier })) },
    ],
  }),
  features: () => ({
    caption: `Feature list, ${MODEL.version}: prior-year cost and visits carry 41% of the weight`,
    columns: [
      { key: 'feature', label: 'Feature' },
      { key: 'weight', label: 'Weight', align: 'right' },
      { key: 'note', label: 'How it treats frontier members' },
    ],
    rows: FEATURES.filter((f) => f.kind === 'Current').map((f) => ({ feature: f.name, weight: `${Math.round(f.weight * 100)}%`, note: f.note })),
  }),
  swaps: () => swapTable(),
  swaps_in: () => swapTable('Enters top 300'),
  before_after: () => ({
    columns: 2,
    children: [
      stat('Frontier gap', `${MODEL.frontierGapPct}% to ${MODEL.frontierGapAfterPct}%`, `Threshold ${MODEL.releaseThresholdPct}%`, 'good'),
      stat('Top 300', `${MODEL.missingFromTop} in, ${MODEL.missingFromTop} out`, 'High-need frontier enter', 'info'),
      stat('Count toward CMS165', `${MODEL.inBpDenominator}`, 'Now reached by outreach', 'good'),
      stat('Accuracy (AUC)', MODEL.auc.toFixed(2), 'Holds steady'),
    ],
  }),
  county_lowvalue: () => ({ kind: 'bar', title: `Low-value spend by county, $K a year (${usdM(STATE.lowValue)} in all)`, series: [{ name: 'Low-value care ($K)', points: COUNTIES.map((c) => ({ label: c.name, value: c.lowValue / 1000 })) }] }),
  ed_projection: () => {
    const cut = STATE.optionAEdCutPct / 100;
    const counties = COUNTIES.filter((c) => c.id === 'lander' || c.id === 'pershing');
    return {
      kind: 'bar',
      title: 'Avoidable ED per 1,000, now and 12 months after options A and C (about 12% lower)',
      series: [
        { name: 'Now', points: counties.map((c) => ({ label: c.name, value: c.edPer1000 })) },
        { name: 'In 12 months', points: counties.map((c) => ({ label: c.name, value: Math.round(c.edPer1000 * (1 - cut)) })) },
      ],
    };
  },
  options: () => ({
    caption: 'Outcomes Accelerator funding options (reach and cost illustrative)',
    columns: [
      { key: 'option', label: 'Option' },
      { key: 'what', label: 'What' },
      { key: 'reach', label: 'Reach', align: 'right' },
      { key: 'cost', label: 'Cost', align: 'right' },
      { key: 'outcome', label: 'Projected outcome' },
      { key: 'time', label: 'Time to impact' },
      { key: 'alignment', label: 'RHTP alignment' },
    ],
    rows: OPTIONS.map((o) => ({ option: o.id, what: o.name, reach: `${num(o.reach)} members`, cost: o.cost ? usdM(o.cost) : 'No new funds', outcome: o.outcome, time: o.time, alignment: 'Outcomes Accelerator' })),
  }),
  reminders_unconfirmed: () => reminderTable('unconfirmed'),
  reminders_r: () => reminderTable('r'),
  networks: () => ({
    caption: 'Participating networks, aggregated and de-identified',
    columns: [
      { key: 'network', label: 'Network' },
      { key: 'sites', label: 'Sites', kind: 'number' },
      { key: 'bp', label: 'BP control', align: 'right' },
      { key: 'crc', label: 'Colorectal screening', align: 'right' },
      { key: 'ed', label: 'Avoidable ED per 1,000', kind: 'number' },
    ],
    rows: [
      { network: 'Sierra Basin Community Health', sites: 7, bp: '58%', crc: '33%', ed: 312 },
      { network: 'Great Basin Rural Clinics', sites: 4, bp: '61%', crc: '36%', ed: 289 },
      { network: 'Humboldt River Health Partners', sites: 3, bp: '55%', crc: '31%', ed: 301 },
      { network: 'Ruby Valley Family Health', sites: 4, bp: '63%', crc: '38%', ed: 284 },
    ],
  }),
};

function swapTable(direction?: 'Enters top 300'): Props {
  const all = getSwaps();
  const rows = direction ? all.filter((r) => r.direction === direction).slice(0, 8) : [...all.filter((r) => r.direction === 'Enters top 300').slice(0, 4), ...all.filter((r) => r.direction === 'Leaves top 300').slice(0, 4)];
  return {
    caption: direction ? `8 of the ${MODEL.missingFromTop} high-need frontier members, de-identified; ${MODEL.inBpDenominator} are in the BP denominator` : `Sample of the ${MODEL.missingFromTop} entering and ${MODEL.missingFromTop} leaving the top 300, de-identified`,
    columns: [
      { key: 'id', label: 'Member' },
      { key: 'change', label: 'Change' },
      { key: 'condition', label: 'Condition' },
      { key: 'drive', label: 'Drive', align: 'right' },
      { key: 'rank', label: 'Rank before to after', align: 'right' },
    ],
    rows: rows.map((r) => ({ id: r.id, change: r.direction, condition: r.condition, drive: `${r.driveMin} min`, rank: `${r.rankBefore} to ${r.rankAfter}` })),
  };
}
