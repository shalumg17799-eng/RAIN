import { useState } from 'react';
import { CONTRACT, COUNTIES, GAP, SEGMENTS, SITES, STATE, num, siteById, usdM } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { FilterSelect, RainCard, ResponsiveTable } from '../shell/rainKit';
import { PmpmTrend, QualityTracker, SegmentPyramid, SiteCompare, Waterfall } from '../cards/insight';
import { CountyMap } from '../cards/state';
import { usePaneContext } from './useWorkbench';

/**
 * Value Insights (P1): cost against expected, the gap waterfall, the
 * segmentation pyramid and the site comparison, with county, site, payer and
 * segment filters. The state lead sees the same workbench at state scope:
 * aggregated, de-identified, by county.
 */
export default function ValueInsights({ access, filter, stateScope }: { access: Access; filter: string | null; stateScope: boolean }) {
  const [county, setCounty] = useState('all');
  const [site, setSite] = useState('all');
  const [segment, setSegment] = useState('all');
  const [selGap, setSelGap] = useState<string | null>(filter === 'gap' ? 'coding' : null);
  const [selSite, setSelSite] = useState<string | null>(null);
  const [selSeg, setSelSeg] = useState<string | null>(null);

  const sites = SITES.filter((s) => (county === 'all' || s.county === county) && (site === 'all' || s.id === site));
  const members = sites.reduce((n, s) => n + s.members, 0);
  const pmpm = members ? Math.round(sites.reduce((n, s) => n + s.pmpm * s.members, 0) / members) : 0;

  const gapLabel = GAP.find((g) => g.id === selGap)?.label;
  const pane = selSite
    ? { label: `${siteById(selSite)?.name} site`, chips: ['Explain this site', 'Compare our sites on cost per member'], kind: 'site' as const, id: selSite }
    : selSeg
      ? { label: SEGMENTS.find((s) => s.id === selSeg)!.label, chips: ['Explain this segment', 'Who are the 1,180?'], kind: 'segment' as const, id: selSeg }
      : selGap
        ? { label: `Gap part: ${gapLabel}`, chips: ['Explain this gap bar', 'What can we still recover by December 31?'], kind: 'gap' as const, id: selGap }
        : stateScope
          ? { label: `State scope: ${STATE.networks} networks, ${num(STATE.members)} members`, chips: [] }
          : { label: `Value Insights: $${pmpm} PMPM across ${num(members)} members`, chips: ['Break down the gap', 'Compare our sites on cost per member'] };
  usePaneContext(stateScope ? { label: pane.label, chips: [] } : pane);

  if (stateScope)
    return (
      <WorkbenchLayout meta={WORKBENCHES.valueInsights} access={access} label="Aggregated, de-identified">
        <RainCard eyebrow="State scope" title={`${STATE.networks} participating networks · ${STATE.sites} sites · ${num(STATE.members)} members`} label="Aggregated, de-identified">
          <ResponsiveTable
            caption="Cost and use by county"
            rows={COUNTIES}
            rowKey={(c) => c.id}
            columns={[
              { key: 'name', label: 'County', render: (c) => <span className="font-semibold">{c.name}</span> },
              { key: 'members', label: 'Members', align: 'right', render: (c) => num(c.members) },
              { key: 'ed', label: 'Avoidable ED / 1,000', align: 'right', render: (c) => c.edPer1000 },
              { key: 'lv', label: 'Low-value care', align: 'right', render: (c) => usdM(c.lowValue, 2) },
              { key: 'bp', label: 'BP control', align: 'right', render: (c) => `${c.bpControlPct}%` },
            ]}
          />
          <p className="mt-2 text-[12px] text-text-muted">
            Avoidable ED {STATE.edPer1000} per 1,000 and {usdM(STATE.lowValue)} in low-value care across the four networks. No identified patient data at state scope.
          </p>
        </RainCard>
        <CountyMap mode="ed" />
      </WorkbenchLayout>
    );

  return (
    <WorkbenchLayout meta={WORKBENCHES.valueInsights} access={access}>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <FilterSelect label="County" value={county} onChange={(v) => { setCounty(v); setSite('all'); }} options={[{ value: 'all', label: 'All counties' }, ...COUNTIES.map((c) => ({ value: c.id, label: c.name }))]} />
        <FilterSelect label="Site" value={site} onChange={setSite} options={[{ value: 'all', label: 'All sites' }, ...SITES.filter((s) => county === 'all' || s.county === county).map((s) => ({ value: s.id, label: s.name }))]} />
        <FilterSelect label="Payer" value="hdhp" onChange={() => undefined} options={[{ value: 'hdhp', label: 'High Desert Health Plan' }]} />
        <FilterSelect label="Segment" value={segment} onChange={(v) => { setSegment(v); setSelSeg(v === 'all' ? null : v); }} options={[{ value: 'all', label: 'All members' }, ...SEGMENTS.map((s) => ({ value: s.id, label: s.label }))]} />
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { label: 'Members in view', value: num(members) },
          { label: 'PMPM in view', value: `$${pmpm}` },
          { label: 'Expected', value: `$${CONTRACT.expectedPmpm}` },
          { label: 'Above expected', value: `${(((pmpm - CONTRACT.expectedPmpm) / CONTRACT.expectedPmpm) * 100).toFixed(1)}%` },
        ].map((t) => (
          <div key={t.label} className="rounded-xl border border-border bg-surface px-3 py-2">
            <p className="text-[11px] font-semibold text-text-muted">{t.label}</p>
            <p className="text-[18px] font-bold tabular-nums text-text">{t.value}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-4 @4xl:grid-cols-2">
        <Waterfall selected={selGap} onSelect={(id) => { setSelGap(id); setSelSite(null); setSelSeg(null); }} />
        <SegmentPyramid selected={selSeg} onSelect={(id) => { setSelSeg(id); setSelSite(null); setSelGap(null); }} />
      </div>
      <div className="grid gap-4 @4xl:grid-cols-2">
        <PmpmTrend compact />
        <SiteCompare metric="pmpm" selected={selSite} onSelect={(id) => { setSelSite(id); setSelGap(null); setSelSeg(null); }} />
      </div>
      <div className="grid gap-4 @4xl:grid-cols-2">
        <QualityTracker />
        <CountyMap mode="ed" />
      </div>
      {county !== 'all' || site !== 'all' ? <p className="text-[12px] text-text-muted">Filters change the members, PMPM and site in view; the gap waterfall and segments are network-wide contract figures.</p> : null}
    </WorkbenchLayout>
  );
}
