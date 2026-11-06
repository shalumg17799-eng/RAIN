/**
 * RAIN v2: the contract holds its shape, the figures add up, every persona's
 * conversation walks, the spec's words are on screen, and the demo never says
 * what it must not.
 *
 *   1. Contract: seven fixed keys per persona; steps reference viz, datasets,
 *      hand-offs and workbenches by id only, and every reference resolves.
 *   2. Figures: every identity the spec's numbers rest on, and every record
 *      set against its headline; JSON tiles quote the master numbers.
 *   3. Flows: every chip routes, the golden path walks, Use Case A carries
 *      capability tags, Use Case B carries none.
 *   4. Spec wording and text rules: verbatim lines present, no em dash, no
 *      internal names, no real plan or partner names.
 *   5. Closed loop: hand-offs, bookings and Linda's reading move the store.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import type { PersonaManifest } from '@core/types';
import { rainClient } from '@/markets/sled/clients/rain/client.manifest';
import ceoM from '@/markets/sled/clients/rain/personas/ceo/manifest';
import cmoM from '@/markets/sled/clients/rain/personas/cmo/manifest';
import cioM from '@/markets/sled/clients/rain/personas/cio/manifest';
import stateM from '@/markets/sled/clients/rain/personas/state/manifest';
import chwM from '@/markets/sled/clients/rain/personas/chw/manifest';
import accessM from '@/markets/sled/clients/rain/personas/access/manifest';
import { rainAnswers } from '@/markets/sled/clients/rain/answers';
import { getRainState, resetRainState, approve, book, recordLindaReading, runAction, requestLaunch, sign, isReleased } from '@/components/rain/shell/store';
import * as C from './_shared/constants';
import { CONTRACT_KEYS, WORKBENCHES } from './_shared/contract';
import type { RainContract } from './_shared/contract';
import { CONTRACTS, HANDOFFS, LAUNCHES } from './contracts';
import { DATASETS } from './_shared/datasets';
import { ALL_SOURCES, PUBLIC_SOURCES, SYNTHETIC_SOURCES } from './_shared/sources';
import { FEATURES, SUBGROUP, getCampaignMembers, getPendingBookings, getReminders, getSwaps, getTeresaWorklist } from './_shared/records';
import { contextSpecs } from './_shared/context';

const sum = (xs: number[]) => xs.reduce((s, x) => s + x, 0);
const KEYS = Object.keys(CONTRACTS) as C.PersonaKey[];
const MANIFESTS: Record<C.PersonaKey, PersonaManifest> = { ceo: ceoM, cmo: cmoM, cio: cioM, state: stateM, chw: chwM, access: accessM };

// ─── 1. Contract ────────────────────────────────────────────────────────────

describe('RAIN data contract', () => {
  it.each(KEYS)('%s has exactly the seven fixed top-level keys', (k) => {
    expect(Object.keys(CONTRACTS[k]).sort()).toEqual([...CONTRACT_KEYS].sort());
  });

  it.each(KEYS)('%s steps reference only viz, datasets, hand-offs and workbenches that exist', (k) => {
    const c: RainContract = CONTRACTS[k];
    const own = new Set(c.workbenches.map((w) => w.id));
    for (const [id, s] of Object.entries(c.steps)) {
      for (const v of s.viz ?? []) expect(c.viz[v], `${k}.${id} → viz ${v}`).toBeDefined();
      if (s.launch) {
        expect(WORKBENCHES[s.launch.workbench], `${id} launch`).toBeDefined();
        expect(own.has(s.launch.workbench), `${id} launches a workbench ${k} cannot open`).toBe(true);
      }
    }
    for (const [id, v] of Object.entries(c.viz)) {
      const ds = (v.props as { dataset?: string }).dataset;
      if (ds) expect(DATASETS[ds], `${k}.${id} dataset ${ds}`).toBeDefined();
      for (const h of ((v.props as { ids?: string[] }).ids ?? [])) expect(HANDOFFS[h], `${k}.${id} hand-off ${h}`).toBeDefined();
      const step = (v.props as { step?: string }).step;
      if (v.type === 'rain.launch_card') expect(LAUNCHES[step!], `${k}.${id} launch step ${step}`).toBeDefined();
    }
  });

  it('every dataset resolves to props', () => {
    for (const [id, f] of Object.entries(DATASETS)) expect(Object.keys(f()).length, id).toBeGreaterThan(0);
  });

  it('every workbench in the catalog is used by at least one persona, and P1 ones are launched by a step', () => {
    const used = new Set(KEYS.flatMap((k) => CONTRACTS[k].workbenches.map((w) => w.id)));
    for (const id of Object.keys(WORKBENCHES)) expect(used.has(id as never), id).toBe(true);
    const launched = new Set(Object.values(LAUNCHES).map((l) => l.workbench));
    for (const w of Object.values(WORKBENCHES)) if (w.priority === 'P1') expect(launched.has(w.id), `${w.id} is P1`).toBe(true);
  });

  it('gives each persona the spec workbenches, Ask AI first in the navigation', () => {
    const expected: Record<C.PersonaKey, Array<[string, string]>> = {
      ceo: [['valueInsights', 'full'], ['qualityGate', 'view'], ['lowValueCare', 'full'], ['dataSources', 'view']],
      cmo: [['qualityGate', 'full'], ['lowValueCare', 'full'], ['valueInsights', 'full'], ['modelGovernance', 'cosign'], ['worklist', 'view']],
      cio: [['modelGovernance', 'full'], ['dataSources', 'full']],
      state: [['countyExplorer', 'full'], ['valueInsights', 'full'], ['rhtpReporting', 'full']],
      chw: [['worklist', 'full'], ['scheduling', 'full']],
      access: [['scheduling', 'full'], ['reminders', 'full']],
    };
    for (const k of KEYS) {
      expect(CONTRACTS[k].workbenches.map((w) => [w.id, w.access]), k).toEqual(expected[k]);
      expect(MANIFESTS[k].features?.navSlots?.[0], k).toBe('ask');
    }
    expect(rainClient.branding.navLabels?.ask).toBe('Ask AI');
  });
});

// ─── 2. Figures ─────────────────────────────────────────────────────────────

describe('RAIN figures reconcile', () => {
  it('ties the contract checkpoint together', () => {
    expect(C.GAP_TOTAL).toBe(C.CONTRACT.actualPmpm - C.CONTRACT.expectedPmpm);
    expect(Math.round(((C.CONTRACT.actualPmpm - C.CONTRACT.expectedPmpm) / C.CONTRACT.expectedPmpm) * 1000) / 10).toBe(C.CONTRACT.abovePct);
    expect(Math.round((26 * C.CONTRACT.members * 12) / 100_000) / 10).toBe(2.9);
    expect(sum(C.SEGMENTS.map((s) => s.members))).toBe(C.CONTRACT.members);
    expect(Math.round((236 / 9400) * 1000) / 10).toBe(2.5);
    expect(Math.round((1180 / 9400) * 1000) / 10).toBe(12.6);
    expect(sum(C.SEGMENTS.map((s) => s.spendPct))).toBe(100);
    expect(Math.round((C.CODING.members / C.CODING.ofHighNeed) * 100)).toBe(C.CODING.sharePct);
    expect(Math.round(((C.CONTRACT.actualPmpm - C.CODING.correctedBenchmark) / C.CODING.correctedBenchmark) * 1000) / 10).toBe(C.CODING.gapAfterPct);
    expect(C.MEASURES.filter(C.isMet).length).toBe(C.CONTRACT.gateMet);
    expect(C.MEASURES.find((m) => m.id === 'CMS165')!.target - C.MEASURES.find((m) => m.id === 'CMS165')!.current).toBe(C.BP.shortPts);
    expect(C.BP.inPerson + C.BP.telehealth).toBe(C.BP.nearControl);
    expect(C.BP.projected).toBeGreaterThanOrEqual(C.BP.needed);
  });

  it('keeps sites, trends and low-value care on the headline numbers', () => {
    expect(sum(C.SITES.map((s) => s.members))).toBe(C.CONTRACT.members);
    expect(Math.round(sum(C.SITES.map((s) => s.pmpm * s.members)) / C.CONTRACT.members)).toBe(C.CONTRACT.actualPmpm);
    expect(Math.round(sum(C.SITES.map((s) => s.imagingPct * s.members)) / C.CONTRACT.members)).toBe(C.LOW_VALUE.networkRatePct);
    expect(sum(C.SITES.map((s) => s.lowValue))).toBe(C.LOW_VALUE.annual);
    expect(Math.round(sum(C.PMPM_TREND.map((p) => p.actual)) / C.PMPM_TREND.length)).toBe(C.CONTRACT.actualPmpm);
    const fromApril = C.WINNEMUCCA_TREND.slice(3).map((p) => p.value);
    expect(Math.round(sum(fromApril) / fromApril.length)).toBe(C.LOW_VALUE.winnemuccaRatePct);
    expect(C.LV_MEASURES.length).toBe(C.LOW_VALUE.measures);
    expect(sum(C.LV_MEASURES.map((m) => m.services))).toBe(C.LOW_VALUE.services);
    expect(sum(C.LV_MEASURES.map((m) => m.dollars))).toBe(C.LOW_VALUE.annual);
    expect(Math.max(...C.LV_MEASURES.map((m) => m.dollars))).toBe(C.LOW_VALUE.lbpImaging);
    expect(Math.round((C.SITES.find((s) => s.id === 'winnemucca')!.lowValue * 0 + 115_000) / C.LOW_VALUE.lbpImaging * 100)).toBe(C.LOW_VALUE.winnemuccaSharePct);
    expect(C.LOCUMS.length).toBe(C.LOW_VALUE.clinicians);
  });

  it('keeps the state view on its totals, with small cells suppressed', () => {
    expect(sum(C.COUNTIES.map((c) => c.members))).toBe(C.STATE.members);
    expect(Math.round(sum(C.COUNTIES.map((c) => c.edPer1000 * c.members)) / C.STATE.members)).toBe(C.STATE.edPer1000);
    expect(sum(C.COUNTIES.map((c) => c.lowValue))).toBe(C.STATE.lowValue);
    expect(C.COUNTIES.length).toBe(C.STATE.counties);
    expect(sum(C.NETWORKS.map((n) => n.sites))).toBe(C.STATE.sites);
    expect(C.NETWORKS.length).toBe(C.STATE.networks);
    for (const id of ['lander', 'pershing']) expect(C.COUNTIES.find((c) => c.id === id)!.pcVisitChangePct).toBe(-C.STATE.pcVisitDropPct);
    expect(C.suppress(8)).toBe('–');
    expect(C.suppress(31)).toBe('31');
    expect(C.LOW_BB_PLACES.length).toBe(C.STATE.lowBroadbandZips);
  });

  it('builds the campaign, worklist, bookings and reminders to the spec counts', () => {
    const all = getCampaignMembers();
    expect(all.length).toBe(C.BP.nearControl);
    expect(all.filter((m) => m.mode === 'Telehealth').length).toBe(C.BP.telehealth);
    expect(all.filter((m) => m.mode === 'In person').length).toBe(C.BP.inPerson);
    expect(all.filter((m) => m.cuff === 'Ship first').length).toBe(C.BP.cuffsToShip);
    for (const m of all) expect(m.mode === 'Telehealth', `${m.id} drive ${m.driveMin}`).toBe(m.driveMin > 60);
    expect(all[0].name).toBe(C.LINDA.name);
    expect(all[0].reasons).toEqual([`BP ${C.LINDA.bp} in ${C.LINDA.bpMonth}`, `${C.LINDA.driveMin}-minute drive`, `No visit in ${C.LINDA.monthsSinceVisit} months`]);
    const teresa = getTeresaWorklist();
    expect(teresa.length).toBe(C.CARE.teresaTop);
    expect(teresa.every((m) => m.siteId === 'winnemucca' || m.siteId === 'battleMountain')).toBe(true);
    const pending = getPendingBookings();
    expect(pending.length).toBe(C.CARE.brandonBookings);
    expect(pending[0].name).toBe(C.LINDA.name);
    expect(pending.filter((b) => b.eligibility === 'Lapsed').length).toBe(1);
    const rem = getReminders();
    expect(rem.filter((r) => r.status === 'No reply yet').length).toBe(C.CARE.brandonUnconfirmed);
    expect(rem.filter((r) => r.status === 'Change requested (R)').length).toBe(C.CARE.brandonRReplies);
    // Teresa's five unanswered calls are on her list, not in Brandon's queue, and no
    // patient with a visit tomorrow still shows as uncalled on her worklist.
    const noCallback = teresa.filter((m) => m.status === 'Left message');
    expect(noCallback.length).toBe(C.CARE.teresaNoCallback);
    expect(noCallback.some((m) => pending.some((b) => b.memberId === m.id))).toBe(false);
    expect(rem.some((r) => r.memberId !== 'M-40107' && teresa.some((m) => m.id === r.memberId))).toBe(false);
    // Every patient has a number to call, in the range reserved for fiction.
    expect(all.every((m) => /^\(775\) 555-01\d\d$/.test(m.phone) && m.bestTime)).toBe(true);
    expect(new Set(teresa.map((m) => m.phone)).size).toBe(teresa.length);
    expect(new Set(all.map((m) => m.name)).size).toBe(all.length);
    expect(all.some((m) => m.name.startsWith('Teresa '))).toBe(false);
    // The campaign's 62 bookings are on the rows, and the reminder patients are among them, at Teresa's sites.
    expect(all.filter((m) => m.status === 'Reached and booked').length).toBe(C.CARE.booked);
    for (const r of rem.filter((x) => x.memberId !== 'M-40107')) {
      const m = all.find((x) => x.id === r.memberId)!;
      expect(m.status).toBe('Reached and booked');
      expect(['winnemucca', 'battleMountain']).toContain(m.siteId);
      expect(r.visit).not.toMatch(/\b1[3-9]:\d\d/);
    }
    // A diabetes reason only for members with diabetes.
    expect(all.filter((m) => m.reasons.includes('Open diabetes gap') && !m.conditions.includes('Type 2 diabetes')).length).toBe(0);
  });

  it('builds the governance figures to the spec counts', () => {
    const swaps = getSwaps();
    expect(swaps.filter((s) => s.direction === 'Enters top 300').length).toBe(C.MODEL.missingFromTop);
    expect(swaps.filter((s) => s.direction === 'Leaves top 300').length).toBe(C.MODEL.missingFromTop);
    expect(swaps.filter((s) => s.inBpDenominator).length).toBe(C.MODEL.inBpDenominator);
    const gap = sum(SUBGROUP.map((g) => (g.town - g.frontier) / g.town)) / SUBGROUP.length;
    expect(Math.round(gap * 100)).toBe(C.MODEL.frontierGapPct);
    const after = sum(SUBGROUP.map((g) => (g.town - g.frontierAfter) / g.town)) / SUBGROUP.length;
    expect(Math.round(after * 100)).toBe(C.MODEL.frontierGapAfterPct);
    expect(Math.round((FEATURES.find((f) => f.id === 'cost')!.weight + FEATURES.find((f) => f.id === 'pcVisits')!.weight) * 100)).toBe(41);
    expect(Math.round(sum(FEATURES.map((f) => f.weight)) * 100)).toBe(100);
    expect(PUBLIC_SOURCES.length).toBe(C.MODEL.publicSources);
    expect(SYNTHETIC_SOURCES.length).toBe(C.MODEL.syntheticSources);
    expect(new Set(ALL_SOURCES.map((s) => s.id)).size).toBe(ALL_SOURCES.length);
  });

  it('quotes the master numbers on every KPI tile', () => {
    const tile = (k: C.PersonaKey, id: string) => CONTRACTS[k].kpis.find((t) => t.id === id)!.value;
    expect(tile('ceo', 'members')).toBe(C.num(C.CONTRACT.members));
    expect(tile('ceo', 'pmpm')).toBe(`$${C.CONTRACT.actualPmpm} / $${C.CONTRACT.expectedPmpm}`);
    expect(tile('ceo', 'above')).toBe(`+${C.CONTRACT.abovePct}%`);
    expect(tile('ceo', 'gate')).toBe(`${C.CONTRACT.gateMet} of ${C.CONTRACT.gateMeasures}`);
    expect(tile('ceo', 'lowValue')).toBe(C.usdK(C.LOW_VALUE.annual));
    expect(tile('ceo', 'ed')).toBe(String(C.ED.per1000));
    expect(tile('ceo', 'days')).toBe(String(C.CONTRACT.daysLeft));
    expect(tile('cmo', 'bp')).toBe('58%');
    expect(tile('cmo', 'lowValue')).toBe(C.num(C.LOW_VALUE.services));
    expect(tile('cmo', 'coding')).toBe(`${C.CODING.members} members`);
    expect(tile('cmo', 'social')).toBe(`${C.MODEL.socialScreenedPct}% of members`);
    expect(tile('cio', 'sources')).toBe(`${C.MODEL.publicSources} public + ${C.MODEL.syntheticSources} synthetic`);
    expect(tile('cio', 'claimsLag')).toBe(`${C.CONTRACT.claimsLagDays} days`);
    expect(tile('cio', 'missing')).toBe(String(C.MODEL.missingFromTop));
    expect(tile('state', 'networks')).toBe(`${C.STATE.networks} (${C.STATE.sites} sites)`);
    expect(tile('state', 'members')).toBe(C.num(C.STATE.members));
    expect(tile('state', 'ed')).toBe(String(C.STATE.edPer1000));
    expect(tile('state', 'lowValue')).toBe(C.usdM(C.STATE.lowValue));
    expect(tile('chw', 'top')).toBe(String(C.CARE.teresaTop));
    expect(tile('chw', 'booked')).toBe(`${C.CARE.booked} of ${C.BP.nearControl}`);
    expect(tile('chw', 'controlled')).toBe(String(C.CARE.controlled));
    expect(tile('access', 'bookings')).toBe(String(C.CARE.brandonBookings));
    expect(tile('access', 'unconfirmed')).toBe(String(C.CARE.brandonUnconfirmed));
    expect(tile('access', 'rReplies')).toBe(String(C.CARE.brandonRReplies));
    for (const k of ['ceo', 'cmo', 'cio', 'state'] as const) expect(CONTRACTS[k].kpis.length, k).toBe(7);
  });
});

// ─── 3. Flows ───────────────────────────────────────────────────────────────

type Flow = { ai_message?: string; suggested_chips?: string[]; capability?: string };

describe('RAIN client', () => {
  it('lists the six operator personas in the spec order, Gregory Haskins default', () => {
    expect(rainClient.personas.map((p) => p.identity.name)).toEqual(['Gregory Haskins, MBA', 'Dr. Naomi Castellanos', 'Raj Malhotra', 'Dr. Lauren Pike', 'Teresa Lopez, CHW', 'Brandon Kee']);
    expect(rainClient.defaultPersonaId).toBe('rain_ceo');
    expect(rainClient.branding.primaryColor).toBe('#003366');
  });
});

describe.each(KEYS)('%s conversation', (k) => {
  const m = MANIFESTS[k];
  const c = CONTRACTS[k];
  const flows = m.flows.chatFlows as Record<string, Flow>;
  const chips = m.flows.chipToFlowKey;
  const useCaseA = c.signals.length > 0;
  beforeEach(resetRainState);

  it('routes every chip to a step that exists', () => {
    for (const [chip, key] of Object.entries(chips)) expect(flows[key], `"${chip}" → "${key}"`).toBeDefined();
  });

  it('routes every chip a step offers, every signal and tile chip, and every query', () => {
    const offered = [...m.ui.initialChips, ...Object.values(m.ui.signalToChip), ...c.queries, ...c.kpis.flatMap((t) => (t.chip ? [t.chip] : []))];
    for (const f of Object.values(flows)) offered.push(...(f.suggested_chips ?? []));
    for (const chip of offered) expect(chips[chip], `unrouted chip "${chip}"`).toBeDefined();
  });

  it('walks the highlighted chips from the greeting to the end without looping', () => {
    const visited: string[] = [];
    let key: string | undefined = m.ui.greetingFlowKey;
    while (key && visited.length < 20) {
      expect(visited, `loops back to ${key}`).not.toContain(key);
      visited.push(key);
      const chip: string | undefined = m.ui.goldenPathChip[key];
      if (!chip) break;
      expect(flows[key].suggested_chips, `${key} highlights "${chip}" without offering it`).toContain(chip);
      key = chips[chip];
    }
    if (useCaseA) expect(visited.map((v) => c.steps[v].step).filter(Boolean)).toEqual([1, 2, 3, 4]);
    else expect(visited.length).toBe(2);
  });

  it(useCaseA ? 'tags every step with a capability that opens the deep-dive' : 'carries no capability tags (task-scoped)', () => {
    const triggers = new Set(m.ui.capabilityCallouts.map((x) => x.trigger));
    for (const [key, f] of Object.entries(flows)) {
      if (key.startsWith('__')) continue;
      if (useCaseA) {
        expect(f.capability, key).toBeTruthy();
        expect(triggers.has(m.ui.flowKeyToCapabilityTrigger[key]), `${key} callout`).toBe(true);
      } else {
        expect(f.capability, key).toBeUndefined();
      }
    }
    if (!useCaseA) {
      expect(Object.keys(m.ui.flowKeyToCapabilityTrigger)).toHaveLength(0);
      expect(m.signals).toHaveLength(0);
    }
  });

  it('says one sentence above its cards, with a short greeting', () => {
    const greeting = flows[m.ui.greetingFlowKey].ai_message!;
    expect(greeting.replace(/Dr\. /g, 'Dr_').split(/(?<=[.?!])\s+(?=[A-Z])/).length).toBeLessThanOrEqual(2);
    for (const [key, f] of Object.entries(flows)) {
      if (key === m.ui.greetingFlowKey || !rainAnswers(c, key)?.length) continue;
      const sentences = f.ai_message!.replace(/\b(\d)\.(\d)/g, '$1_$2').replace(/Dr\. /g, 'Dr_').split(/(?<=[.?!])\s+(?=[A-Z])/);
      expect(sentences.length, `${key}: "${f.ai_message}"`).toBe(1);
    }
  });

  it('draws only types it declares, and a launch card on every launching step', () => {
    const declared = new Set((m.catalog ?? []).map((e) => e.type));
    for (const key of Object.keys(c.steps)) {
      const specs = rainAnswers(c, key) ?? [];
      for (const s of specs) if (s.type.startsWith('rain.')) expect(declared.has(s.type), `${key} draws ${s.type}`).toBe(true);
      if (c.steps[key].launch) expect(specs.some((s) => s.type === 'rain.launch_card'), `${key} launch card`).toBe(true);
    }
  });

  it('lands typed questions on their steps, with or without punctuation', () => {
    for (const q of c.queries) {
      const key = chips[q];
      expect(m.flows.matchUtterance?.(q.toLowerCase().replace(/\?/g, ''))).toBe(key);
    }
    expect(m.flows.matchUtterance?.('what is the weather in reno')).toBeNull();
  });

  it('records a launch when a launching step is entered', () => {
    const launching = Object.entries(c.steps).find(([, s]) => s.launch);
    if (!launching) return;
    m.flows.onFlowEnter?.(launching[0]);
    expect(getRainState().launch?.workbench).toBe(launching[1].launch!.workbench);
  });
});

// ─── 4. Spec wording and text rules ─────────────────────────────────────────

describe('RAIN keeps every spec fact, in short form', () => {
  const said = (k: C.PersonaKey, id: string) => [CONTRACTS[k].steps[id].ai, ...(CONTRACTS[k].steps[id].points ?? [])].join(' ');
  it.each([
    ['ceo', 'ceo_brief', ['$412', '$386', '6.7%', '2 of the 3', '58 days', '$618K']],
    ['ceo', 'ceo_gap', ['$12', '73', '3.1%', '$8', '312 vs 251', '$5.50', '$0.50', '1,180']],
    ['ceo', 'ceo_recover', ['$398', '180', 'CMS165', '268', '3 of 5', '300', '$1.1M']],
    ['ceo', 'ceo_board', ['top 300', '73-member coding list', 'Dr. Castellanos']],
    ['cmo', 'cmo_winnemucca', ['27%', '9%', 'April', '71%', '$162K', 'red-flag', 'missing order set']],
    ['cmo', 'cmo_close', ['210', '180', '65%', '268', 'CMS165', '4 points', 'Q1']],
    ['cmo', 'cmo_campaign', ['144 in person', '268 telehealth', '37']],
    ['cio', 'cio_subgroup', ['31%', '74-minute', '190', 'cost-as-proxy']],
    ['cio', 'cio_fix', ['18%', '3%', '57', '41 of the 57', 'accuracy holds steady']],
    ['cio', 'cio_packet', ['model card', 'before and after', 'sign-off', 'pending-fix banner', 'ADT']],
    ['state', 'st_brief', ['14%', 'Lander and Pershing', '$2.4M', 'six frontier ZIP codes']],
    ['state', 'st_funds', ['A:', 'B:', 'C:', '12%', 'a third of the $2.4M', 'six low-broadband ZIP codes']],
    ['state', 'st_summary', ['people served', 'by county', 'PDF or CSV']],
    ['chw', 'chw_brief', ['Dr. Castellanos', '412 patients', '46 of them']],
    ['access', 'acc_brief', ['23 bookings', '9 visits tomorrow', '4 patients replied R']],
  ] as const)('%s %s', (k, id, facts) => {
    const text = said(k, id).toLowerCase();
    for (const f of facts) expect(text, f).toContain(f.toLowerCase());
  });

  it('keeps every signal card to one short line', () => {
    for (const k of KEYS) for (const s of CONTRACTS[k].signals) expect(s.description.length, `${k} ${s.id}`).toBeLessThanOrEqual(100);
  });

  it('answers the spec context chips in the pane', () => {
    expect(contextSpecs('mode', 'M-40107').map((s) => JSON.stringify(s.props)).join(' ')).toContain('Telehealth recommended: 81-minute drive, broadband available, visit type eligible.');
    expect(CONTRACTS.chw.steps.chw_ctx_rank.asks).toContain('Why is she ranked first?');
    expect(CONTRACTS.chw.steps.chw_ctx_talk.asks).toContain('Give me talking points in Spanish for this patient');
    expect(CONTRACTS.access.steps.acc_ctx_slots.asks).toContain('What other slots work for an 81-minute drive?');
    expect(CONTRACTS.cmo.steps.cmo_ctx_rank.asks).toContain('Explain this ranking');
    expect(CONTRACTS.state.steps.st_ctx_lander.asks).toContain('Lander County: what changed since January?');
  });
});

function files(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) files(p, out);
    else if (/\.(tsx?|json)$/.test(n) && !n.endsWith('.test.ts')) out.push(p);
  }
  return out;
}

describe('RAIN text rules', () => {
  const SRC = join(__dirname, '..', '..');
  const all = [join(SRC, 'data/rain'), join(SRC, 'components/rain'), join(SRC, 'markets/sled/clients/rain')].flatMap((d) => files(d));
  const text = all.map((f) => [f, readFileSync(f, 'utf8')] as const);

  it('uses no em dash anywhere', () => {
    for (const [f, t] of text) expect(t.includes('—'), f).toBe(false);
  });

  it('names no internal staff, real partner, real plan or licensed tool', () => {
    const banned = /\b(Srini|Shankar|Prafull|Rama|Lam|Venkat|Bobby|Renown|Kaiser|WellnessPointe|Milliman|G0136|Anthem|Molina|CareSource|SilverSummit)\b/;
    for (const [f, t] of text) expect(t.match(banned)?.[0], f).toBeUndefined();
  });
});

// ─── 5. Closed loop ─────────────────────────────────────────────────────────

describe('RAIN closed loop', () => {
  beforeEach(resetRainState);

  it('hands off only on approval, and the care team progress flows back', () => {
    expect(getRainState().approved.bp412).toBeUndefined();
    runAction('approve:outreach300,coding73');
    expect(getRainState().approved).toMatchObject({ outreach300: true, coding73: true });
    approve('bp412');
    expect(getRainState().approved.bp412).toBe(true);
    book('M-40107', 'S1');
    expect(getRainState().campaign.booked).toBe(C.CARE.booked + 1);
    book('M-40107', 'S1');
    expect(getRainState().campaign.booked).toBe(C.CARE.booked + 1);
    recordLindaReading();
    recordLindaReading();
    expect(getRainState().campaign.controlled).toBe(C.CARE.controlled + 1);
  });

  it('releases the model only after both signatures', () => {
    runAction('preview:fix');
    runAction('sign:cio');
    expect(isReleased()).toBe(false);
    sign('cmo');
    expect(isReleased()).toBe(true);
  });

  it('lets a pane answer highlight rows in the workbench', () => {
    runAction('highlight:campaignTop10');
    expect(getRainState().highlight).toEqual(getCampaignMembers().slice(0, 10).map((m) => m.id));
    runAction('highlight:teresaTop5');
    expect(getRainState().highlight).toHaveLength(5);
    expect(CONTRACTS.cmo.steps.cmo_412.action).toBe('highlight:campaignTop10');
  });

  it('numbers launches so a follower opens each one once', () => {
    requestLaunch('cmo_campaign', LAUNCHES.cmo_campaign);
    const first = getRainState().launch!.seq;
    requestLaunch('cmo_campaign', LAUNCHES.cmo_campaign);
    expect(getRainState().launch!.seq).toBe(first + 1);
    resetRainState();
    expect(getRainState().launch).toBeNull();
  });
});
