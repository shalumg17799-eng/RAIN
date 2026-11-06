/**
 * Use Case A insight visuals: the PMPM trend, the gap waterfall, the
 * segmentation pyramid, the scenario panel, the 2027 projection, site
 * comparisons and the low-value measure list. Each reads the master numbers
 * (`data/rain/_shared/constants.ts`), so a card, a tile and a sentence can
 * never disagree. Used in answers and on the workbenches alike.
 */
import { Bar as RBar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { CODING, CONTRACT, COHORT, GAP, GAP_TOTAL, LV_MEASURES, MEASURES, PMPM_TREND, SEGMENTS, SITES, isMet, num, usd, usdK, usdM } from '@/data/rain/_shared/constants';
import { Meter, RainCard, Pill } from '../shell/rainKit';
import { categoryAxis, useWidth } from '../shell/useWidth';

const AXIS = { stroke: 'var(--color-chart-axis)', fontSize: 11, tickLine: false } as const;
const chart = (i: number) => `var(--color-chart-${(i % 8) + 1})`;

export function PmpmTrend({ title = 'PMPM, actual vs expected, by month since January', points, compact = false }: { title?: string; points?: string[]; compact?: boolean }) {
  const data = PMPM_TREND.map((p) => ({ label: p.month, Actual: p.actual, Expected: CONTRACT.expectedPmpm }));
  return (
    <RainCard eyebrow="Cost against expected" title={title} points={points}>
      <div className={compact ? 'h-[150px]' : 'h-[200px]'}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis domain={[370, 430]} tickFormatter={(v) => `$${v}`} {...AXIS} width={44} />
            <Tooltip formatter={(v) => `$${v}`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="Actual" stroke="var(--color-critical)" strokeWidth={2.5} dot={{ r: 2.5 }} />
            <Line type="monotone" dataKey="Expected" stroke={chart(0)} strokeDasharray="5 4" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[12px] text-text-muted">
        Year to date: ${CONTRACT.actualPmpm} vs ${CONTRACT.expectedPmpm}, +{CONTRACT.abovePct}%.
      </p>
    </RainCard>
  );
}

/** Expected to actual in four labelled steps (spec: "waterfall chart: expected $386 to actual $412"). */
export function Waterfall({ points, onSelect, selected }: { points?: string[]; onSelect?: (id: string) => void; selected?: string | null }) {
  const lo = 380;
  const hi = 416;
  const pct = (v: number) => ((v - lo) / (hi - lo)) * 100;
  const steps = GAP.map((g, i) => {
    const from = CONTRACT.expectedPmpm + GAP.slice(0, i).reduce((s, x) => s + x.value, 0);
    return { ...g, from, to: from + g.value };
  });
  const rows = [
    { id: 'expected', label: 'Expected', from: lo, to: CONTRACT.expectedPmpm, value: CONTRACT.expectedPmpm, note: 'Contract benchmark', total: true },
    ...steps.map((s) => ({ id: s.id, label: s.label, from: s.from, to: s.to, value: s.value, note: s.note, total: false })),
    { id: 'actual', label: 'Actual', from: lo, to: CONTRACT.actualPmpm, value: CONTRACT.actualPmpm, note: `+${CONTRACT.abovePct}% above expected`, total: true },
  ];
  return (
    <RainCard eyebrow="The $26 gap" title={`Expected $${CONTRACT.expectedPmpm} to actual $${CONTRACT.actualPmpm} PMPM`} points={points}>
      <ol className="space-y-2" aria-label="Gap waterfall">
        {rows.map((r) => {
          const clickable = !!onSelect && !r.total;
          const body = (
            <>
              <span className="w-[112px] flex-shrink-0 text-[12.5px] font-semibold text-text @lg:w-[150px]">{r.label}</span>
              <span className="min-w-0 flex-1">
                <Meter
                  className="h-6 rounded"
                  spans={[
                    {
                      from: pct(r.total ? lo : r.from),
                      to: Math.max(pct(r.total ? lo : r.from) + 1.2, pct(r.to)),
                      className: r.total ? (r.id === 'actual' ? 'fill-critical/80' : 'fill-brand') : r.id === 'coding' ? 'fill-warning' : r.id === 'other' ? 'fill-text-subtle/50' : 'fill-critical/60',
                    },
                  ]}
                />
              </span>
              <span className="w-[64px] flex-shrink-0 text-right text-[12.5px] font-semibold tabular-nums text-text">{r.total ? `$${r.value}` : `+${usd(r.value, r.value % 1 ? 2 : 0)}`}</span>
            </>
          );
          return (
            <li key={r.id}>
              {clickable ? (
                <button type="button" onClick={() => onSelect?.(r.id)} aria-pressed={selected === r.id} className={`flex w-full items-center gap-2 rounded-lg p-1 text-left hover:bg-surface-2/70 ${selected === r.id ? 'bg-brand/[0.07] ring-1 ring-brand/30' : ''}`}>
                  {body}
                </button>
              ) : (
                <div className="flex items-center gap-2 p-1">{body}</div>
              )}
              <p className="ml-[120px] text-[11.5px] text-text-subtle @lg:ml-[158px]">{r.note}</p>
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-[12px] text-text-muted">
        ${GAP[0].value} + ${GAP[1].value} + ${GAP[2].value.toFixed(2)} + ${GAP[3].value.toFixed(2)} = ${GAP_TOTAL} PMPM. Axis starts at ${lo}.
      </p>
    </RainCard>
  );
}

/** Impactability segmentation: 236 / 1,180 / 7,984 with share of spend. */
export function SegmentPyramid({ focus, points, onSelect, selected }: { focus?: 'highNeed' | 'impactable' | 'stable'; points?: string[]; onSelect?: (id: string) => void; selected?: string | null }) {
  const widths = { highNeed: 'w-[34%]', impactable: 'w-[62%]', stable: 'w-full' } as const;
  const tone = { highNeed: 'bg-critical/80 text-white', impactable: 'bg-warning text-text', stable: 'bg-brand/15 text-text' } as const;
  return (
    <RainCard eyebrow="Member segmentation" title="Who drives cost, and who can still change" points={points}>
      <div className="space-y-2">
        {SEGMENTS.map((s) => {
          const on = focus === s.id || selected === s.id;
          const block = (
            <div className="flex flex-col items-center">
              <div className={`flex min-h-[44px] min-w-[150px] items-center justify-center rounded-lg px-2 text-center ${widths[s.id]} ${tone[s.id]} ${on ? 'ring-2 ring-brand ring-offset-2' : ''}`}>
                <span className="text-[13px] font-bold tabular-nums">{num(s.members)}</span>
                <span className="ml-1.5 text-[11.5px] font-semibold">{s.sharePct}%</span>
              </div>
            </div>
          );
          return (
            <div key={s.id} className="grid grid-cols-1 items-center gap-1 @lg:grid-cols-[minmax(0,1fr)_minmax(0,220px)] @lg:gap-3">
              {onSelect ? (
                <button type="button" onClick={() => onSelect(s.id)} aria-pressed={selected === s.id} className="w-full rounded-lg p-0.5 hover:bg-surface-2/60">
                  {block}
                </button>
              ) : (
                block
              )}
              <div className="text-center @lg:text-left">
                <p className="text-[12.5px] font-semibold text-text">
                  {s.label} <span className="font-normal text-text-muted">· {s.spendPct}% of spend</span>
                </p>
                <p className="text-[11.5px] text-text-subtle">{s.action}</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[12px] text-text-muted">
        {num(SEGMENTS[0].members + SEGMENTS[1].members + SEGMENTS[2].members)} members. {CODING.members} high-need not yet recaptured; top {COHORT.topRanked} impactable ranked for outreach.
      </p>
    </RainCard>
  );
}

/** Do nothing against the three moves, to December 31. */
export function ScenarioPanel({ focus, points }: { focus?: 'nothing'; points?: string[] }) {
  const bars = [
    { label: 'Gap to expected', nothing: `${CONTRACT.abovePct}%`, moves: `About ${CODING.gapAfterPct}%`, n: CONTRACT.abovePct, m: CODING.gapAfterPct, max: 8, lowerBetter: true },
    { label: 'Quality gate', nothing: `${CONTRACT.gateMet} of ${CONTRACT.gateMeasures}`, moves: `${CONTRACT.gateNeeded} of ${CONTRACT.gateMeasures}`, n: CONTRACT.gateMet, m: CONTRACT.gateNeeded, max: 5, lowerBetter: false },
    { label: '12-month avoided cost', nothing: '$0', moves: usdM(COHORT.avoidedCost12m), n: 0, m: 1.1, max: 1.4, lowerBetter: false },
  ];
  const timeline = [
    { when: 'This week', what: `Coding recapture for ${CODING.members}; BP campaign to the care team` },
    { when: 'Weeks 1 to 6', what: 'Telehealth rechecks with home cuffs' },
    { when: 'December 31', what: `Gate at ${CONTRACT.gateNeeded} of ${CONTRACT.gateMeasures}: shared savings kept` },
    { when: '2027', what: `About ${usdM(COHORT.avoidedCost12m)} avoided from top ${COHORT.topRanked} outreach` },
  ];
  return (
    <RainCard eyebrow="Scenario" title={focus === 'nothing' ? 'If nothing changes by December 31' : 'Do nothing vs. the three moves'} points={points}>
      <div className="grid gap-3 @lg:grid-cols-3">
        {bars.map((b) => (
          <div key={b.label} className="rounded-xl border border-border-subtle p-3">
            <p className="text-[12px] font-semibold text-text">{b.label}</p>
            <div className="mt-2 space-y-1.5">
              <ScenarioRow name="Do nothing" value={b.nothing} pct={(b.n / b.max) * 100} tone="fill-critical/70" emphasis={focus === 'nothing'} />
              {focus !== 'nothing' && <ScenarioRow name="Three moves" value={b.moves} pct={(b.m / b.max) * 100} tone="fill-success" emphasis />}
            </div>
          </div>
        ))}
      </div>
      {focus === 'nothing' ? (
        <p className="mt-3 rounded-xl bg-critical-subtle px-3 py-2 text-[12.5px] text-critical-700">No shared savings this year; a weak 2027 renegotiation.</p>
      ) : (
        <ol className="mt-3 grid gap-2 @lg:grid-cols-4" aria-label="Timeline to December 31">
          {timeline.map((t, i) => (
            <li key={t.when} className="relative rounded-xl bg-surface-2/70 p-2.5">
              <span className="text-[11px] font-bold uppercase tracking-wide text-brand">
                {i + 1}. {t.when}
              </span>
              <p className="mt-0.5 text-[12px] leading-snug text-text">{t.what}</p>
            </li>
          ))}
        </ol>
      )}
    </RainCard>
  );
}

function ScenarioRow({ name, value, pct, tone, emphasis }: { name: string; value: string; pct: number; tone: string; emphasis?: boolean }) {
  return (
    <div>
      <div className="flex justify-between text-[11.5px]">
        <span className="text-text-muted">{name}</span>
        <span className={`tabular-nums ${emphasis ? 'font-bold text-text' : 'text-text-muted'}`}>{value}</span>
      </div>
      <Meter className="mt-0.5 h-2" spans={[{ from: 0, to: Math.max(2, Math.min(100, pct)), className: tone }]} />
    </div>
  );
}

type SiteMetric = 'pmpm' | 'imaging' | 'lowValue' | 'social';

const SOCIAL: Record<string, number> = { elko: 44, wells: 31, winnemucca: 35, battleMountain: 29, lovelock: 33, ely: 41, fallon: 42 };

const SITE_METRIC: Record<SiteMetric, { title: string; eyebrow: string; value: (id: string) => number; fmt: (v: number) => string; ref?: { value: number; label: string }; worst: (v: number) => boolean }> = {
  pmpm: { eyebrow: 'Sites', title: 'Cost per member per month, by site', value: (id) => SITES.find((s) => s.id === id)!.pmpm, fmt: (v) => `$${v}`, ref: { value: CONTRACT.actualPmpm, label: `Network $${CONTRACT.actualPmpm}` }, worst: (v) => v >= 430 },
  imaging: { eyebrow: 'Low back pain imaging', title: 'Imaging rate by site, share of eligible visits', value: (id) => SITES.find((s) => s.id === id)!.imagingPct, fmt: (v) => `${v}%`, ref: { value: 9, label: 'Network 9%' }, worst: (v) => v >= 20 },
  lowValue: { eyebrow: 'Low-value care', title: 'Low-value spend by site, annualized', value: (id) => SITES.find((s) => s.id === id)!.lowValue / 1000, fmt: (v) => `$${v}K`, worst: (v) => v >= 150 },
  social: { eyebrow: 'Social needs', title: 'Members with a social needs screening, by site', value: (id) => SOCIAL[id], fmt: (v) => `${v}%`, ref: { value: 38, label: 'Network 38%' }, worst: (v) => v < 33 },
};

export function SiteCompare({ metric = 'pmpm', points, onSelect, selected }: { metric?: SiteMetric; points?: string[]; onSelect?: (id: string) => void; selected?: string | null }) {
  const m = SITE_METRIC[metric];
  const data = SITES.map((s) => ({ id: s.id, label: s.name, value: m.value(s.id) }));
  const { ref, width } = useWidth<HTMLDivElement>();
  return (
    <RainCard eyebrow={m.eyebrow} title={m.title} points={points}>
      <div ref={ref} className="h-[230px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
            <XAxis dataKey="label" {...AXIS} {...categoryAxis(width, (l) => l.replace('Battle Mountain', 'Battle Mtn'))} />
            <YAxis tickFormatter={(v) => m.fmt(Number(v))} {...AXIS} width={46} domain={metric === 'pmpm' ? [370, 445] : [0, 'auto']} />
            <Tooltip formatter={(v) => m.fmt(Number(v))} />
            {m.ref && <ReferenceLine y={m.ref.value} stroke="var(--color-chart-axis)" strokeDasharray="4 4" />}
            <RBar dataKey="value" radius={[3, 3, 0, 0]} onClick={onSelect ? (d) => onSelect(String((d as unknown as { id: string }).id)) : undefined} cursor={onSelect ? 'pointer' : undefined}>
              {data.map((d) => (
                <Cell key={d.id} fill={selected === d.id ? 'var(--color-brand)' : m.worst(d.value) ? 'var(--color-critical)' : chart(0)} fillOpacity={selected && selected !== d.id ? 0.55 : 1} />
              ))}
            </RBar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[11.5px] text-text-subtle">
        {m.ref ? `Dashed line: ${m.ref.label.toLowerCase()}. ` : ''}
        {onSelect ? 'Select a bar to explain that site in the Ask AI pane.' : ''}
      </p>
    </RainCard>
  );
}

/** The low-value measure library, largest first. */
export function LvMeasures({ limit = 14, points, onSelect, selected, site }: { limit?: number; points?: string[]; onSelect?: (id: string) => void; selected?: string | null; site?: string }) {
  const rows = [...LV_MEASURES].sort((a, b) => b.dollars - a.dollars).slice(0, limit);
  const max = rows[0].dollars;
  return (
    <RainCard eyebrow="Low-value care" title={limit < 14 ? `The ${limit} largest low-value measures` : 'The 14-measure library, by annual spend'} points={points} aside={site ? <Pill tone="brand">{site}</Pill> : undefined}>
      <ul className="divide-y divide-border-subtle">
        {rows.map((r) => {
          const body = (
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 py-2">
              <span className="min-w-0 text-[13px] text-text">
                {r.name} <span className="text-[11px] text-text-subtle">· {r.basis}</span>
              </span>
              <span className="text-right text-[13px] font-semibold tabular-nums text-text">{usdK(r.dollars)}</span>
              <span className="col-span-2 flex items-center gap-2">
                <span className="min-w-0 flex-1">
                  <Meter className="h-1.5" max={max} spans={[{ from: 0, to: r.dollars, className: 'fill-critical/70' }]} />
                </span>
                <span className="w-[86px] text-right text-[11px] text-text-muted">{num(r.services)} services</span>
              </span>
            </div>
          );
          return (
            <li key={r.id}>
              {onSelect ? (
                <button type="button" onClick={() => onSelect(r.id)} aria-pressed={selected === r.id} className={`w-full rounded-lg px-1 text-left hover:bg-surface-2/60 ${selected === r.id ? 'bg-brand/[0.07]' : ''}`}>
                  {body}
                </button>
              ) : (
                body
              )}
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-[12px] text-text-muted">All 14 measures: {num(2140)} services, {usdK(618_000)} a year (Choosing Wisely and USPSTF based).</p>
    </RainCard>
  );
}

/** The quality gate tracker: five measures, current, target, status. */
export function QualityTracker({ points, onSelect, selected, projected = false }: { points?: string[]; onSelect?: (id: string) => void; selected?: string | null; projected?: boolean }) {
  const met = MEASURES.filter(isMet).length;
  return (
    <RainCard
      eyebrow="Quality gate"
      title={`${met} of ${MEASURES.length} met · ${CONTRACT.gateNeeded} needed for shared savings`}
      points={points}
      aside={<Pill tone={met >= CONTRACT.gateNeeded ? 'good' : 'critical'}>{met >= CONTRACT.gateNeeded ? 'Gate passes' : 'Gate at risk'}</Pill>}
    >
      <ul className="space-y-2.5">
        {MEASURES.map((m) => {
          const ok = isMet(m);
          const gapPts = Math.abs(m.target - m.current);
          const body = (
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1">
              <span className="min-w-0 text-[13px] font-semibold text-text">
                {m.name} <span className="font-normal text-text-subtle">({m.id}{m.higherIsBetter ? '' : ', lower is better'})</span>
              </span>
              <Pill tone={ok ? 'good' : 'critical'}>{ok ? 'Met' : m.id === 'CMS165' ? 'Not met: about 180 more' : `Not met: ${gapPts} pts`}</Pill>
              <span className="col-span-2">
                <Meter
                  className="h-2.5"
                  markers={[m.target]}
                  spans={[
                    { from: 0, to: m.current, className: ok ? 'fill-success' : 'fill-critical/70' },
                    ...(projected ? [{ from: Math.min(m.current, m.projected), to: Math.max(m.current, m.projected), className: 'fill-brand/40' }] : []),
                  ]}
                />
                <span className="mt-0.5 flex justify-between text-[11.5px] text-text-muted">
                  <span>
                    Current <b className="text-text">{m.current}%</b>
                    {projected && <> · projected {m.projected}%</>}
                  </span>
                  <span>
                    Target {m.higherIsBetter ? `${m.target}% or higher` : `${m.target}% or lower`}
                  </span>
                </span>
              </span>
            </div>
          );
          return (
            <li key={m.id}>
              {onSelect ? (
                <button type="button" onClick={() => onSelect(m.id)} aria-pressed={selected === m.id} className={`w-full rounded-lg p-1.5 text-left hover:bg-surface-2/60 ${selected === m.id ? 'bg-brand/[0.07] ring-1 ring-brand/30' : ''}`}>
                  {body}
                </button>
              ) : (
                body
              )}
            </li>
          );
        })}
      </ul>
    </RainCard>
  );
}

