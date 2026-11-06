/**
 * Data and AI governance visuals (Raj Malhotra; co-signed by the CMO): the
 * model card, the subgroup check, the drive-time scatter, the feature table,
 * the before and after comparison and the members who change places.
 */
import { Bar as RBar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { BP, MODEL } from '@/data/rain/_shared/constants';
import type { ModelFeature, SwapRow } from '@/data/rain/_shared/records';
import { FEATURES, SUBGROUP, getAccessPoints, getSwaps } from '@/data/rain/_shared/records';
import { Pill, RainCard, ResponsiveTable } from '../shell/rainKit';
import { categoryAxis, useWidth } from '../shell/useWidth';
import { useRainState } from '../shell/store';

const AXIS = { stroke: 'var(--color-chart-axis)', fontSize: 11, tickLine: false } as const;

export function ModelCard({ points }: { points?: string[] }) {
  const { fixPreview, signed } = useRainState();
  const released = signed.cio && signed.cmo;
  const rows = [
    ['Model', `${MODEL.name} ${released ? MODEL.candidate : MODEL.version}`],
    ['Intended use', 'Rank rising-risk members for care team outreach'],
    ['Training data', 'Synthetic claims and EHR for 9,400 attributed members'],
    ['Release threshold', `Subgroup gap under ${MODEL.releaseThresholdPct}%`],
    ['Accuracy', `AUC ${MODEL.auc.toFixed(2)} against the clinical review sample`],
    ['Owner', 'CIO, with CMO co-sign'],
  ];
  return (
    <RainCard
      eyebrow="Model card"
      title={`${MODEL.name} ${released ? MODEL.candidate : MODEL.version}`}
      points={points}
      aside={released ? <Pill tone="good">Subgroup check passed</Pill> : <Pill tone="critical">Subgroup check failed</Pill>}
    >
      <dl className="grid gap-x-4 gap-y-1.5 text-[12.5px] @lg:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">{k}</dt>
            <dd className="text-text">{v}</dd>
          </div>
        ))}
      </dl>
      <div className={`mt-3 rounded-xl px-3 py-2 text-[12.5px] ${released ? 'bg-success-subtle text-success-700' : 'bg-critical-subtle text-critical-700'}`}>
        {released
          ? `Frontier gap ${MODEL.frontierGapAfterPct}%, inside the ${MODEL.releaseThresholdPct}% threshold. Released to the care team.`
          : `Frontier ZIPs ranked ${MODEL.frontierGapPct}% lower than similar members in town. ${MODEL.missingFromTop} high-need frontier members missing from the top 300.${fixPreview ? ` Access-adjusted ${MODEL.candidate} brings it to ${MODEL.frontierGapAfterPct}%.` : ''}`}
      </div>
    </RainCard>
  );
}

/** Average risk rank by condition group, frontier vs town (and after the fix). */
export function SubgroupBars({ points, after }: { points?: string[]; after?: boolean }) {
  const { fixPreview } = useRainState();
  const showAfter = after ?? fixPreview;
  const data = SUBGROUP.map((g) => ({ label: g.group, Town: g.town, Frontier: g.frontier, ...(showAfter ? { 'Frontier, access-adjusted': g.frontierAfter } : {}) }));
  const { ref, width } = useWidth<HTMLDivElement>();
  return (
    <RainCard eyebrow="Subgroup check" title="Average risk rank by condition group (percentile)" points={points}>
      <div ref={ref} className="h-[250px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
            <XAxis dataKey="label" {...AXIS} {...categoryAxis(width, (l) => l.replace('COPD or asthma', 'COPD/asthma'))} />
            <YAxis {...AXIS} width={32} domain={[0, 80]} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <RBar dataKey="Town" fill="var(--color-chart-1)" radius={[3, 3, 0, 0]} />
            <RBar dataKey="Frontier" fill="var(--color-critical)" radius={[3, 3, 0, 0]} />
            {showAfter && <RBar dataKey="Frontier, access-adjusted" fill="var(--color-success)" radius={[3, 3, 0, 0]} />}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[12px] text-text-muted">Same conditions and labs; frontier ranks {MODEL.frontierGapPct}% lower on average.</p>
    </RainCard>
  );
}

/** Drive time against primary care visits, frontier vs town. */
export function DriveScatter({ points }: { points?: string[] }) {
  const pts = getAccessPoints();
  return (
    <RainCard eyebrow="Access" title="Drive time vs. primary care visits, last 12 months" points={points}>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 6, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-chart-grid)" />
            <XAxis type="number" dataKey="driveMin" name="Drive" unit=" min" {...AXIS} />
            <YAxis type="number" dataKey="visits" name="Visits" {...AXIS} width={28} allowDecimals={false} />
            <ZAxis range={[28, 28]} />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Scatter name="Town" data={pts.filter((p) => !p.frontier)} fill="var(--color-chart-1)" />
            <Scatter name="Frontier" data={pts.filter((p) => p.frontier)} fill="var(--color-critical)" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[12px] text-text-muted">Frontier: {MODEL.medianDriveMin}-minute median drive, {MODEL.fewerVisitsPct}% fewer visits. Sample of 90.</p>
    </RainCard>
  );
}

export function FeatureTable({ points, onSelect, selected }: { points?: string[]; onSelect?: (f: ModelFeature) => void; selected?: string | null }) {
  const { fixPreview, signed } = useRainState();
  const withNew = fixPreview || (signed.cio && signed.cmo);
  const rows = FEATURES.filter((f) => withNew || f.kind === 'Current');
  return (
    <RainCard eyebrow="Features" title={withNew ? `Feature list, ${MODEL.candidate} (access-adjusted)` : `Feature list, ${MODEL.version}`} points={points}>
      <ResponsiveTable
        caption="Model features and weights"
        rows={rows}
        rowKey={(f) => f.id}
        onRowClick={onSelect}
        selectedKey={selected}
        columns={[
          { key: 'name', label: 'Feature', render: (f) => <span className="font-semibold">{f.name}</span> },
          { key: 'weight', label: 'Weight', align: 'right', render: (f) => `${Math.round(f.weight * 100)}%` },
          { key: 'kind', label: 'Status', render: (f) => <Pill tone={f.kind === 'Current' ? 'neutral' : 'good'}>{f.kind}</Pill> },
          { key: 'note', label: 'How it treats frontier members', wideOnly: true, render: (f) => <span className="text-[12px] text-text-muted">{f.note}</span> },
        ]}
      />
      {onSelect && <p className="mt-2 text-[11.5px] text-text-subtle">Select a feature to explain it in the Ask AI pane.</p>}
    </RainCard>
  );
}

export function BeforeAfter({ points }: { points?: string[] }) {
  const items = [
    { label: 'Frontier gap', before: `${MODEL.frontierGapPct}%`, after: `${MODEL.frontierGapAfterPct}%`, note: `Release threshold ${MODEL.releaseThresholdPct}%` },
    { label: 'High-need frontier in top 300', before: `Missing ${MODEL.missingFromTop}`, after: `+${MODEL.missingFromTop} enter`, note: `${MODEL.missingFromTop} lower-need town members leave` },
    { label: 'BP campaign impact', before: `${BP.nearControl} members`, after: `${MODEL.inBpDenominator} more in the BP measure reached`, note: 'Helps the quality gate' },
    { label: 'Accuracy (AUC)', before: MODEL.auc.toFixed(2), after: MODEL.auc.toFixed(2), note: 'Holds steady' },
  ];
  return (
    <RainCard eyebrow="Before and after" title={`${MODEL.version} vs. access-adjusted ${MODEL.candidate}`} points={points}>
      <div className="grid gap-2 @lg:grid-cols-2">
        {items.map((i) => (
          <div key={i.label} className="rounded-xl border border-border-subtle p-3">
            <p className="text-[11.5px] font-semibold uppercase tracking-wide text-text-subtle">{i.label}</p>
            <p className="mt-1 flex flex-wrap items-baseline gap-x-2 text-[14px]">
              <span className="text-text-muted line-through decoration-text-subtle">{i.before}</span>
              <span className="font-bold text-success-700">{i.after}</span>
            </p>
            <p className="text-[11.5px] text-text-muted">{i.note}</p>
          </div>
        ))}
      </div>
    </RainCard>
  );
}

export function SwapTable({ direction, points }: { direction?: SwapRow['direction']; points?: string[] }) {
  const rows = getSwaps().filter((r) => !direction || r.direction === direction);
  const shown = direction ? rows.slice(0, 8) : [...rows.filter((r) => r.direction === 'Enters top 300').slice(0, 4), ...rows.filter((r) => r.direction === 'Leaves top 300').slice(0, 4)];
  return (
    <RainCard eyebrow="De-identified" title={direction ? `${MODEL.missingFromTop} high-need frontier members` : `${MODEL.missingFromTop} enter and ${MODEL.missingFromTop} leave the top 300`} points={points}>
      <ResponsiveTable
        caption="Members changing places in the top 300"
        rows={shown}
        rowKey={(r) => r.id}
        columns={[
          { key: 'id', label: 'Member' },
          { key: 'direction', label: 'Change', render: (r) => <Pill tone={r.direction === 'Enters top 300' ? 'good' : 'neutral'}>{r.direction}</Pill> },
          { key: 'condition', label: 'Condition' },
          { key: 'driveMin', label: 'Drive', align: 'right', render: (r) => `${r.driveMin} min` },
          { key: 'rank', label: 'Rank before → after', align: 'right', render: (r) => `${r.rankBefore} → ${r.rankAfter}` },
        ]}
      />
      <p className="mt-2 text-[12px] text-text-muted">Showing {shown.length} of {rows.length}. {direction ? `${MODEL.inBpDenominator} of the ${MODEL.missingFromTop} are in the BP measure denominator.` : ''}</p>
    </RainCard>
  );
}
