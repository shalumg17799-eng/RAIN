/**
 * State-scope visuals (Dr. Pike, and the CIO's frontier map): the Nevada
 * county map with layer toggles, the county comparison table with suppressed
 * small cells, the funding options, and the county trends. All aggregated
 * and de-identified. The map is inline SVG on simplified outlines (plan D16).
 */
import { useState } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { County, CountyId } from '@/data/rain/_shared/constants';
import { COUNTIES, OPTIONS, STATE, num, usdM } from '@/data/rain/_shared/constants';
import { COUNTY_LABEL, COUNTY_SHAPES, FRONTIER_POINTS, OTHER_COUNTIES, SITE_POINTS, STATE_OUTLINE, pathOf, project, viewHeight } from '@/data/rain/_shared/geo';
import { Pill, RainCard, ResponsiveTable, Segmented } from '../shell/rainKit';
import { useRainState } from '../shell/store';

const AXIS = { stroke: 'var(--color-chart-axis)', fontSize: 11, tickLine: false } as const;
const W = 560;
const H = viewHeight(W);

export type MapLayer = 'ed' | 'places' | 'svi' | 'hpsa' | 'broadband';

const LAYERS: Record<MapLayer, { label: string; source: string; value: (c: County) => number; fmt: (c: County) => string; color: string; lo: number; hi: number; legend: [string, string] }> = {
  ed: { label: 'Avoidable ED', source: 'Aggregated claims', value: (c) => c.edPer1000, fmt: (c) => `${c.edPer1000}`, color: 'var(--color-critical)', lo: 270, hi: 360, legend: ['270 per 1,000', '360'] },
  places: { label: 'Hypertension (PLACES)', source: 'CDC PLACES', value: (c) => c.htnPct, fmt: (c) => `${c.htnPct}%`, color: 'var(--color-chart-1)', lo: 27, hi: 36, legend: ['27%', '36%'] },
  svi: { label: 'Vulnerability (SVI)', source: 'CDC/ATSDR SVI', value: (c) => c.svi, fmt: (c) => c.svi.toFixed(2), color: 'var(--color-chart-4)', lo: 0.35, hi: 0.75, legend: ['0.35', '0.75'] },
  hpsa: { label: 'Shortage area (HPSA)', source: 'HRSA HPSA', value: (c) => (c.hpsa === 'Whole county' ? 1 : 0.45), fmt: (c) => (c.hpsa === 'Whole county' ? 'Whole' : 'Part'), color: 'var(--color-warning)', lo: 0, hi: 1, legend: ['Part of county', 'Whole county'] },
  broadband: { label: 'Broadband (FCC)', source: 'FCC Broadband Map', value: (c) => 100 - c.broadbandPct, fmt: (c) => `${c.broadbandPct}%`, color: 'var(--color-chart-4)', lo: 10, hi: 50, legend: ['More video-ready', 'Less video-ready'] },
};

export function CountyMap({
  mode = 'ed',
  points,
  onSelect,
  selected,
  layer: controlledLayer,
  onLayer,
}: {
  mode?: 'ed' | 'layers' | 'frontier' | 'broadband' | 'target';
  points?: string[];
  onSelect?: (id: CountyId) => void;
  selected?: CountyId | null;
  layer?: MapLayer;
  onLayer?: (l: MapLayer) => void;
}) {
  const { targetCounties } = useRainState();
  const [ownLayer, setOwnLayer] = useState<MapLayer>(mode === 'broadband' ? 'broadband' : 'ed');
  const layer = controlledLayer ?? ownLayer;
  const setLayer = onLayer ?? setOwnLayer;
  const L = LAYERS[mode === 'frontier' ? 'ed' : layer];
  const HALO = { paintOrder: 'stroke' as const, stroke: 'var(--color-surface)', strokeWidth: 3, strokeLinejoin: 'round' as const };
  const targets = mode === 'target' ? (targetCounties.length ? targetCounties : ['lander', 'pershing']) : targetCounties;
  const showBroadbandPlaces = mode === 'broadband' || mode === 'target' || ((mode === 'layers' || !!onLayer) && layer === 'broadband');
  const places = mode === 'frontier' ? FRONTIER_POINTS : showBroadbandPlaces ? FRONTIER_POINTS.filter((f) => f.lowBroadband) : [];
  const shade = (c: County) => {
    if (mode === 'frontier') return 0.1;
    const t = (L.value(c) - L.lo) / (L.hi - L.lo);
    return 0.15 + Math.max(0, Math.min(1, t)) * 0.7;
  };
  const title =
    mode === 'frontier' ? 'Frontier places in the network counties' : mode === 'target' ? 'Where Outcomes Accelerator funds go first' : mode === 'broadband' ? 'Broadband for video visits by county' : `${L.label} by county`;
  return (
    <RainCard eyebrow={mode === 'frontier' ? 'Census ZCTA · USDA RUCC' : 'County view'} title={title} points={points} label="Aggregated, de-identified">
      {(mode === 'layers' || onLayer) && (
        <div className="mb-2">
          <Segmented<MapLayer>
            label="Map layer"
            value={layer}
            onChange={setLayer}
            options={[
              { value: 'ed', label: 'Avoidable ED' },
              { value: 'places', label: 'PLACES' },
              { value: 'svi', label: 'SVI' },
              { value: 'hpsa', label: 'HPSA' },
              { value: 'broadband', label: 'Broadband' },
            ]}
          />
        </div>
      )}
      <div className="mx-auto w-full max-w-[560px]">
        <svg viewBox={`0 0 ${W} ${H.toFixed(0)}`} className="h-auto w-full" role="img" aria-label={`${title}. ${COUNTIES.map((c) => `${c.name} ${L.fmt(c)}`).join(', ')}.`}>
          <path d={pathOf(STATE_OUTLINE, W)} fill="var(--color-surface-2)" stroke="var(--color-border)" strokeWidth={1.5} />
          {OTHER_COUNTIES.map((o) => {
            const p = project(o.label, W);
            return (
              <g key={o.name} pointerEvents="none">
                <path d={pathOf(o.shape, W)} fill="var(--color-surface)" stroke="var(--color-border)" strokeWidth={1} strokeDasharray="4 3" />
                <text x={p.x} y={p.y} textAnchor="middle" fontSize="12" fill="var(--color-text-subtle)">
                  {o.name}
                </text>
              </g>
            );
          })}
          {COUNTIES.map((c) => {
            const isTarget = targets.includes(c.id);
            const isSel = selected === c.id;
            return (
              <g key={c.id}>
                <path
                  d={pathOf(COUNTY_SHAPES[c.id], W)}
                  fill={mode === 'target' ? (isTarget ? 'var(--color-brand)' : 'var(--color-surface)') : mode === 'frontier' ? 'var(--color-brand)' : L.color}
                  fillOpacity={mode === 'target' ? (isTarget ? 0.75 : 1) : shade(c)}
                  stroke={isSel ? 'var(--color-text)' : 'var(--color-surface)'}
                  strokeWidth={isSel ? 3 : 1.5}
                  className={onSelect ? 'cursor-pointer outline-none hover:opacity-90 focus-visible:opacity-90' : undefined}
                  onClick={onSelect ? () => onSelect(c.id) : undefined}
                  onKeyDown={onSelect ? (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(c.id)) : undefined}
                  tabIndex={onSelect ? 0 : undefined}
                  role={onSelect ? 'button' : undefined}
                  aria-label={onSelect ? `${c.name} County` : undefined}
                />
                {(mode === 'ed' || mode === 'layers') && layer === 'ed' && c.hpsa === 'Whole county' && (
                  <path d={pathOf(COUNTY_SHAPES[c.id], W)} fill="url(#rain-hatch)" pointerEvents="none" />
                )}
              </g>
            );
          })}
          <defs>
            <pattern id="rain-hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="8" stroke="var(--color-text)" strokeOpacity="0.35" strokeWidth="2" />
            </pattern>
          </defs>
          {COUNTIES.map((c) => {
            const p = project(COUNTY_LABEL[c.id], W);
            return (
              <g key={`l-${c.id}`} pointerEvents="none">
                <text x={p.x} y={p.y} textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--color-text)" {...HALO}>
                  {c.name}
                </text>
                {mode !== 'frontier' && mode !== 'target' && (
                  <text x={p.x} y={p.y + 17} textAnchor="middle" fontSize="13" fill="var(--color-text)" {...HALO}>
                    {L.fmt(c)}
                  </text>
                )}
              </g>
            );
          })}
          {Object.entries(SITE_POINTS).map(([id, at]) => {
              const p = project(at, W);
              return <rect key={id} x={p.x - 4} y={p.y - 4} width={8} height={8} fill="var(--color-brand)" stroke="var(--color-surface)" strokeWidth={1.5} pointerEvents="none" />;
            })}
          {places.map((f) => {
            const p = project(f.at, W);
            const left = f.side === 'left';
            return (
              <g key={f.name} pointerEvents="none">
                <circle cx={p.x} cy={p.y} r={5.5} fill="var(--color-critical)" stroke="var(--color-surface)" strokeWidth={2} />
                <text x={left ? p.x - 9 : p.x + 9} y={p.y + 4 + (f.dy ?? 0)} textAnchor={left ? 'end' : 'start'} fontSize="12" fontWeight="600" fill="var(--color-text)" {...HALO}>
                  {f.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-text-muted">
        {mode === 'target' ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-sm bg-brand/75" aria-hidden="true" /> Option A counties
            <span className="ml-3 h-2.5 w-2.5 rounded-full bg-critical" aria-hidden="true" /> Option C mobile clinic places
          </span>
        ) : mode === 'frontier' ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-critical" aria-hidden="true" /> {FRONTIER_POINTS.length} frontier places (RUCC and FORHP), named by town
          </span>
        ) : (
          <>
            <span className="inline-flex items-center gap-1.5">
              <svg viewBox="0 0 64 12" className="h-3 w-16 rounded-sm border border-border-subtle" aria-hidden="true">
                {[0.18, 0.4, 0.62, 0.85].map((o, i) => (
                  <rect key={o} x={i * 16} y={0} width={16} height={12} fill={L.color} fillOpacity={o} />
                ))}
              </svg>
              {L.legend[0]} to {L.legend[1]} · {L.source}
            </span>
            {layer === 'ed' && <span>Hatched: whole-county shortage area</span>}
            {showBroadbandPlaces && (
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-critical" aria-hidden="true" /> ZIP areas under {STATE.broadbandFloorPct}% video-ready
              </span>
            )}
          </>
        )}
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 bg-brand" aria-hidden="true" /> Network sites
        </span>
        <span>Dashed: other counties. Simplified outlines.</span>
      </div>
      {onSelect && <p className="mt-1 text-[11.5px] text-text-subtle">Select a county to ask about it in the Ask AI pane.</p>}
    </RainCard>
  );
}

/** Side-by-side county table; heat on the need columns; counts under 11 suppressed. */
export function CountyTable({ points, onSelect, selected }: { points?: string[]; onSelect?: (id: CountyId) => void; selected?: CountyId | null }) {
  const heat = (v: number, lo: number, hi: number) => {
    const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
    return t > 0.66 ? 'bg-critical-subtle font-semibold text-critical-700' : t > 0.33 ? 'bg-warning-subtle text-warning-700' : '';
  };
  return (
    <RainCard eyebrow="County comparison" title="Six rural counties side by side" points={points} label="Aggregated, de-identified">
      <ResponsiveTable
        caption="County comparison"
        rows={COUNTIES}
        rowKey={(c) => c.id}
        onRowClick={onSelect ? (c) => onSelect(c.id) : undefined}
        selectedKey={selected}
        columns={[
          { key: 'name', label: 'County', render: (c) => <span className="font-semibold">{c.name}</span> },
          { key: 'members', label: 'Members', align: 'right', render: (c) => num(c.members) },
          { key: 'htn', label: 'Hypertension', align: 'right', render: (c) => <span className={`rounded px-1 ${heat(c.htnPct, 28, 35)}`}>{c.htnPct}%</span> },
          { key: 'dm', label: 'Diabetes', align: 'right', render: (c) => `${c.diabetesPct}%`, wideOnly: true },
          { key: 'svi', label: 'SVI', align: 'right', render: (c) => <span className={`rounded px-1 ${heat(c.svi, 0.4, 0.72)}`}>{c.svi.toFixed(2)}</span> },
          { key: 'hpsa', label: 'HPSA', render: (c) => <Pill tone={c.hpsa === 'Whole county' ? 'critical' : 'warning'}>{c.hpsa === 'Whole county' ? 'Whole' : 'Part'}</Pill> },
          { key: 'bb', label: 'Broadband', align: 'right', render: (c) => <span className={`rounded px-1 ${heat(100 - c.broadbandPct, 15, 48)}`}>{c.broadbandPct}%</span> },
          { key: 'pc', label: 'PC visits', align: 'right', render: (c) => <span className={`rounded px-1 ${heat(-c.pcVisitChangePct, 2, 14)}`}>{c.pcVisitChangePct}%</span> },
          { key: 'ed', label: 'ED / 1,000', align: 'right', render: (c) => <span className={`rounded px-1 ${heat(c.edPer1000, 280, 350)}`}>{c.edPer1000}</span> },
          { key: 'hf', label: 'HF members', align: 'right', render: (c) => (c.heartFailure < STATE.suppressUnder ? <span title="Suppressed: fewer than 11">–</span> : num(c.heartFailure)) },
        ]}
      />
      <p className="mt-2 text-[11.5px] text-text-muted">
        Sources: CDC PLACES, CDC SVI, HRSA HPSA, FCC Broadband Map, RAIN aggregated claims. PC visits: change since January. ED: avoidable visits. HF: heart failure. A dash is a suppressed cell (fewer than {STATE.suppressUnder}). Prevalence and SVI values are illustrative.
      </p>
    </RainCard>
  );
}

export function OptionTable({ points }: { points?: string[] }) {
  return (
    <RainCard eyebrow="Funding options" title="Outcomes Accelerator: three options compared" points={points} label="Aggregated, de-identified">
      <ResponsiveTable
        caption="Funding options"
        rows={[...OPTIONS]}
        rowKey={(o) => o.id}
        columns={[
          { key: 'id', label: 'Option', render: (o) => <span className="font-bold text-brand">{o.id}</span> },
          { key: 'name', label: 'What', render: (o) => <span className="font-semibold">{o.name}</span> },
          { key: 'reach', label: 'Reach', align: 'right', render: (o) => `${num(o.reach)} members` },
          { key: 'cost', label: 'Cost', align: 'right', render: (o) => (o.cost ? usdM(o.cost) : 'No new funds') },
          { key: 'outcome', label: 'Projected outcome', render: (o) => <span className="text-[12px]">{o.outcome}</span> },
          { key: 'time', label: 'Time to impact' },
          { key: 'align', label: 'RHTP alignment', render: () => 'Outcomes Accelerator' },
        ]}
      />
      <p className="mt-2 rounded-xl bg-brand/[0.06] px-3 py-2 text-[12.5px] text-text">
        Recommendation: fund <b>A and C</b> together and run <b>B</b> as a no-cost data service. Reach and cost are illustrative.
      </p>
    </RainCard>
  );
}

/** Primary care visits indexed to January, Lander and Pershing against the other four. */
export function PcTrend({ points }: { points?: string[] }) {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];
  const lp = [100, 97, 95, 93, 91, 89, 88, 87, 86];
  const others = [100, 99, 98, 98, 97, 97, 97, 96, 97];
  const data = months.map((m, i) => ({ label: m, 'Lander and Pershing': lp[i], 'Other four counties': others[i] }));
  return (
    <RainCard eyebrow="Since January" title="Primary care visits, indexed to January = 100" points={points} label="Aggregated, de-identified">
      <div className="h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis domain={[80, 102]} {...AXIS} width={32} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="Lander and Pershing" stroke="var(--color-critical)" strokeWidth={2.5} dot={{ r: 2.5 }} />
            <Line type="monotone" dataKey="Other four counties" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[12px] text-text-muted">Members moved into managed care on January 1. Monthly path is illustrative; the September change is the reported figure.</p>
    </RainCard>
  );
}

