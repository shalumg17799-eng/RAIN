/**
 * RAIN: the signal cards, hand-offs and secondary tiles agree with the master
 * numbers in _shared/constants.ts.
 *
 * The story: Sierra Basin's value-based contract runs $412 against $386 PMPM
 * across 9,400 members (6.7% above, about $2.9M a year) with 58 days left. The
 * quality gate needs 3 of 5 measures and meets 2; BP control (CMS165) is 58%
 * against 65%, so about 180 more of the 412 near-control members must reach
 * control. Low-value care is 2,140 services across 14 measures ($618K), led by
 * low back pain imaging ($162K, 71% from Winnemucca since April). The CIO's
 * model ranks frontier ZIPs 18% lower and leaves 57 high-need members out of
 * the top 300. The state view covers 31,600 members in 6 counties and 4
 * networks (18 sites), with primary care down 14% in Lander and Pershing.
 *
 * rain.test.ts already reconciles the constants with each other and pins the
 * headline KPI tiles and the step prose. This file covers what it leaves out:
 * every signal card's description and metric, the hand-off counts, the
 * remaining KPI tiles, the cited sources against the Data Sources workbench,
 * the measure projections, and Linda's calendar.
 */
import { describe, it, expect } from 'vitest';
import * as C from './_shared/constants';
import { CONTRACTS, HANDOFFS } from './contracts';
import { ALL_SOURCES } from './_shared/sources';

const signal = (k: C.PersonaKey, id: string) => CONTRACTS[k].signals.find((s) => s.id === id)!;
const said = (k: C.PersonaKey, id: string) => {
  const s = signal(k, id);
  return `${s.description} ${s.metric}`;
};
const tile = (k: C.PersonaKey, id: string) => CONTRACTS[k].kpis.find((t) => t.id === id)!.value;
const measure = (id: C.MeasureId) => C.MEASURES.find((m) => m.id === id)!;

describe('RAIN signal cards quote the master numbers', () => {
  it('CEO: cost above expected', () => {
    const t = said('ceo', 'SIG-CEO-1');
    for (const f of [
      `$${C.CONTRACT.actualPmpm} vs $${C.CONTRACT.expectedPmpm}`,
      C.num(C.CONTRACT.members),
      `${C.CONTRACT.abovePct}%`,
      C.usdM(C.CONTRACT.annualGap),
    ]) {
      expect(t, f).toContain(f);
    }
  });

  it('CEO: quality gate at risk', () => {
    const t = said('ceo', 'SIG-CEO-2');
    expect(t).toContain(`${C.CONTRACT.gateMet} of the ${C.CONTRACT.gateNeeded} measures needed`);
    expect(t).toContain(`${C.BP.shortPts} points short`);
    expect(t).toContain(`${C.CONTRACT.daysLeft} days left`);
    expect(signal('ceo', 'SIG-CEO-2').metric).toBe(
      `${C.CONTRACT.gateMet} of ${C.CONTRACT.gateMeasures} met · needs ${C.CONTRACT.gateNeeded}`,
    );
  });

  it('CEO: low-value care, led by the largest library item', () => {
    const t = said('ceo', 'SIG-CEO-3');
    expect(t).toContain(`${C.num(C.LOW_VALUE.services)} services across ${C.LOW_VALUE.measures} measures`);
    expect(signal('ceo', 'SIG-CEO-3').metric).toBe(`${C.usdK(C.LOW_VALUE.annual)} a year`);
    const largest = [...C.LV_MEASURES].sort((a, b) => b.dollars - a.dollars)[0];
    expect(largest.name.toLowerCase()).toContain('low back pain');
    expect(t).toContain('Low back pain imaging is the largest item');
  });

  it('CMO: BP control, low back pain imaging and coding recapture', () => {
    const bp = measure('CMS165');
    const t1 = said('cmo', 'SIG-CMO-1');
    expect(t1).toContain(`${bp.current}% vs a ${bp.target}% target`);
    expect(t1).toContain(`About ${C.BP.needed} more needed`);
    expect(t1).toContain(`${C.BP.nearControl} are within ${C.BP.withinPoints} points`);
    expect(bp.target - bp.current).toBe(C.BP.shortPts);

    const t2 = said('cmo', 'SIG-CMO-2');
    expect(t2).toContain(C.usdK(C.LOW_VALUE.lbpImaging));
    expect(t2).toContain(`${C.LOW_VALUE.winnemuccaSharePct}%`);
    expect(t2).toContain(C.LOW_VALUE.rotationMonth);

    const t3 = said('cmo', 'SIG-CMO-3');
    expect(t3).toContain(`${C.CODING.members} high-need members`);
    expect(t3).toContain(`${C.CODING.understatedPct}%`);
  });

  it('keeps the near-control count inside the hypertensive population', () => {
    expect(C.BP.nearControl).toBeLessThan(C.BP.hypertensive);
  });

  it.todo(
    'BP denominator: the spec gives 2,250 hypertensive members and "about 180 more" to close the 7-point gap, but 7 points of 2,250 is about 158 (180 needs about 2,570) — left: both figures are the spec\'s own, and the talk track speaks 180 and 210; the spec owner decides which to change',
  );

  it('CIO: subgroup gap, claims lag and social screening', () => {
    const t1 = said('cio', 'SIG-CIO-1');
    expect(t1).toContain(`${C.MODEL.frontierGapPct}%`);
    expect(t1).toContain(`${C.MODEL.missingFromTop} high-need miss the top ${C.COHORT.topRanked}`);
    const t2 = said('cio', 'SIG-CIO-2');
    expect(t2).toContain(`${C.CONTRACT.claimsLagDays} days`);
    expect(t2.toLowerCase()).toContain(C.MODEL.adtLag.toLowerCase());
    expect(said('cio', 'SIG-CIO-3')).toContain(`${C.MODEL.socialScreenedPct}%`);
  });

  it('State: primary care drop, low-value spend and broadband', () => {
    const dropped = C.COUNTIES.filter((c) => c.pcVisitChangePct === -C.STATE.pcVisitDropPct);
    const t1 = said('state', 'SIG-ST-1');
    expect(t1).toContain(`${C.STATE.pcVisitDropPct}% in ${dropped.map((c) => c.name).join(' and ')}`);
    expect(signal('state', 'SIG-ST-1').metric).toBe(`-${C.STATE.pcVisitDropPct}% in ${dropped.length} counties`);
    // The indexed trend ends on the same drop.
    expect(100 - C.PC_TREND.landerPershing[C.PC_TREND.landerPershing.length - 1]).toBe(C.STATE.pcVisitDropPct);

    const t2 = said('state', 'SIG-ST-2');
    expect(t2).toContain(C.usdM(C.STATE.lowValue));
    expect(t2).toContain(`${C.STATE.networks} networks (${C.STATE.sites} sites)`);

    const t3 = said('state', 'SIG-ST-3');
    expect(t3).toContain('Six frontier ZIP codes');
    expect(C.LOW_BB_PLACES).toHaveLength(6);
    expect(t3).toContain(`under ${C.STATE.broadbandFloorPct}%`);
    expect(signal('state', 'SIG-ST-3').metric).toBe(`${C.STATE.lowBroadbandZips} ZIP areas under ${C.STATE.broadbandFloorPct}%`);
  });
});

describe('RAIN hand-offs and the remaining tiles', () => {
  it('hands off exactly the counts the constants hold', () => {
    expect(HANDOFFS.outreach300.count).toBe(C.COHORT.topRanked);
    expect(HANDOFFS.coding73.count).toBe(C.CODING.members);
    expect(HANDOFFS.bp412.count).toBe(C.BP.nearControl);
    expect(HANDOFFS.shareNetworks.count).toBe(C.STATE.networks);
    for (const h of Object.values(HANDOFFS)) {
      if (/\(\d+\)/.test(h.title)) expect(h.title, h.id).toContain(`(${h.count})`);
    }
  });

  it('reads every measure tile off the measure it names', () => {
    expect(tile('cmo', 'bp')).toBe(`${measure('CMS165').current}%`);
    expect(tile('cmo', 'a1c')).toBe(`${measure('CMS122').current}%`);
    expect(tile('cmo', 'crc')).toBe(`${measure('CMS130').current}%`);
    expect(tile('cmo', 'gate')).toBe(`${C.CONTRACT.gateMet} of ${C.CONTRACT.gateMeasures}`);
  });

  it('quotes the CIO, state and care-team tiles rain.test.ts does not', () => {
    expect(tile('cio', 'adtLag')).toBe(C.MODEL.adtLag);
    expect(tile('cio', 'social')).toBe(`${C.MODEL.socialScreenedPct}%`);
    expect(tile('cio', 'subgroup')).toBe('Failed');
    expect(C.MODEL.frontierGapPct).toBeGreaterThan(C.MODEL.releaseThresholdPct);
    expect(C.MODEL.frontierGapAfterPct).toBeLessThanOrEqual(C.MODEL.releaseThresholdPct);
    expect(tile('state', 'counties')).toBe(`${C.STATE.counties} rural`);
    expect(tile('state', 'hpsa')).toBe(`${C.STATE.hpsaCounties} of ${C.STATE.counties}`);
    expect(tile('state', 'suppressed')).toBe(`Counts under ${C.STATE.suppressUnder}`);
    expect(tile('chw', 'campaign')).toBe(String(C.BP.nearControl));
    expect(tile('chw', 'noCallback')).toBe(String(C.CARE.teresaNoCallback));
    expect(tile('chw', 'open')).toBe(String(C.CARE.teresaOpen));
    expect(tile('access', 'sites')).toBe(`${C.SITES.length} sites`);
  });

  it('keeps the HPSA tile true of the counties', () => {
    // "6 of 6": every county carries a shortage designation, whole or part.
    expect(C.COUNTIES.filter((c) => c.hpsa)).toHaveLength(C.STATE.hpsaCounties);
  });

  it('gives Sierra Basin its own seven sites among the four networks', () => {
    expect(C.NETWORKS[0].name).toBe('Sierra Basin Community Health');
    expect(C.NETWORKS[0].sites).toBe(C.SITES.length);
    expect(C.NETWORKS[0].bpControlPct).toBe(measure('CMS165').current);
    expect(C.NETWORKS[0].edPer1000).toBe(C.ED.per1000);
  });

  it('meets three of five measures on the projection, the number the gate needs', () => {
    const projectedMet = C.MEASURES.filter((m) => C.isMet({ ...m, current: m.projected }));
    expect(projectedMet).toHaveLength(C.CONTRACT.gateNeeded);
    expect(projectedMet.map((m) => m.id)).toContain('CMS165');
  });

  it('sizes funding option B to the whole state view', () => {
    const b = C.OPTIONS.find((o) => o.id === 'B')!;
    expect(b.reach).toBe(C.STATE.members);
    expect(b.outcome).toContain(C.usdM(C.STATE.lowValue));
    const a = C.OPTIONS.find((o) => o.id === 'A')!;
    expect(a.outcome).toContain(`${C.STATE.optionAEdCutPct}%`);
  });

  it('ends every monthly series in September, the end of the Q3 claims the freshness line names', () => {
    expect(C.FRESHNESS).toContain('Q3');
    expect(C.FRESHNESS).toContain(`${C.CONTRACT.claimsLagDays}-day lag`);
    expect(C.PMPM_TREND.at(-1)!.month).toBe('Sep');
    expect(C.WINNEMUCCA_TREND.at(-1)!.month).toBe('Sep');
    expect(C.PC_TREND.months.at(-1)).toBe('Sep');
    expect(C.WINNEMUCCA_TREND.findIndex((p) => p.month === C.LOW_VALUE.rotationMonth.slice(0, 3))).toBe(3);
  });
});

describe('RAIN cited sources', () => {
  const words = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().split(' ').filter(Boolean);
  const listed = (label: string) =>
    ALL_SOURCES.some((src) => {
      const have = new Set(words(`${src.id} ${src.name} ${src.provides} ${src.usedFor}`));
      return words(label).every((w) => have.has(w) || have.has(`${w}s`) || (w.endsWith('s') && have.has(w.slice(0, -1))));
    });
  const cited = [
    ...new Set(
      Object.values(CONTRACTS).flatMap((c) => [
        ...c.signals.flatMap((s) => s.sources),
        ...Object.values(c.steps).flatMap((s) => s.sources ?? []),
      ]),
    ),
  ].sort();

  /**
   * Labels the cards and steps cite that the Data Sources workbench does not
   * list. Pinned so a new unlisted label fails here; see the todo below.
   */
  const UNLISTED = [
    'Aggregated Claims',
    'All aggregated sources',
    'All executive data sources',
    'BP Campaign Worklist',
    'Care Plan Templates',
    'Contact Log',
    'Data Quality Monitor',
    'Data Sources Registry',
    'EHR Schedule',
    'Grantee Registry',
    'Model Card',
    'Pipeline Monitor',
    'Screening Tool',
    'Worklist Hand-off',
  ];

  it('cites only listed sources, apart from the known unlisted labels', () => {
    expect(cited.filter((s) => !listed(s))).toEqual(UNLISTED);
  });

  it.todo(
    'sources: signal/step sources in ceo/cmo/cio/state/chw/access.json name labels absent from _shared/sources.ts ALL_SOURCES (the Data Sources workbench): Aggregated Claims, BP Campaign Worklist, Care Plan Templates, Contact Log, Data Quality Monitor, Data Sources Registry, EHR Schedule, Grantee Registry, Model Card, Pipeline Monitor, Screening Tool, Worklist Hand-off (plus the umbrella labels "All aggregated sources" / "All executive data sources")',
  );
});

describe('RAIN Linda’s calendar', () => {
  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  /** "Nov 5" in the 2026 contract year. */
  const weekday = (date: string) => DAYS[new Date(`${date}, 2026`).getDay()];

  it('puts each dated item on the weekday it is called', () => {
    expect(weekday(C.LINDA.visit.date)).toBe(C.LINDA.visit.day);
    expect(weekday(C.LINDA.mobileClinic.date)).toBe(C.LINDA.mobileClinic.day);
    const [refillDay, refillDate] = C.LINDA.refill.due.split(', ');
    expect(weekday(refillDate)).toBe(refillDay);
    expect(C.LINDA.visit.es).toContain('jueves 5 de nov');
  });

  it('orders the visit, the refill and the mobile clinic', () => {
    const t = (d: string) => new Date(`${d}, 2026`).getTime();
    expect(t(C.LINDA.visit.date)).toBeLessThan(t(C.LINDA.refill.due.split(', ')[1]));
    expect(t(C.LINDA.refill.due.split(', ')[1])).toBeLessThan(t(C.LINDA.mobileClinic.date));
  });

  it('keeps her last reading above goal and her visit reading at or under it', () => {
    expect(C.LINDA.bp).toBe(C.bpText(C.LINDA.last));
    expect(C.LINDA.last.sys).toBeGreaterThanOrEqual(C.LINDA.goal.sys);
    expect(C.LINDA.visitReading.sys).toBeLessThan(C.LINDA.goal.sys);
    expect(C.LINDA.visitReading.dia).toBeLessThan(C.LINDA.goal.dia);
    expect(C.LINDA.bpMonth).toBe(C.LINDA.last.month.en);
  });
});
