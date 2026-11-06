/**
 * Quality and campaign visuals (Dr. Castellanos, and the care team's view of
 * the same campaign): the Winnemucca imaging trend, measure projections, the
 * visit-mode split, the campaign preview, member tables and progress.
 */
import { Bar as RBar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BP, LOCUMS, LOW_VALUE, MEASURES, WINNEMUCCA_TREND, num } from '@/data/rain/_shared/constants';
import { getCampaignMembers } from '@/data/rain/_shared/records';
import { Meter, Pill, RainCard, ResponsiveTable } from '../shell/rainKit';
import { memberColumns } from './columns';
import { useRainState } from '../shell/store';

const AXIS = { stroke: 'var(--color-chart-axis)', fontSize: 11, tickLine: false } as const;

/** Winnemucca's monthly imaging rate with the April rotation marked. */
export function AnnotatedTrend({ points }: { points?: string[] }) {
  const data = WINNEMUCCA_TREND.map((p) => ({ label: p.month, Winnemucca: p.value, Network: LOW_VALUE.networkRatePct }));
  return (
    <RainCard eyebrow="Winnemucca" title="Low back pain imaging rate by month" points={points}>
      <div className="h-[190px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 14, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis tickFormatter={(v) => `${v}%`} {...AXIS} width={38} domain={[0, 35]} />
            <Tooltip formatter={(v) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <ReferenceLine x="Apr" stroke="var(--color-warning)" strokeWidth={2} label={{ value: 'Locum rotation begins', fontSize: 10, position: 'insideTopLeft', fill: 'var(--color-text)' }} />
            <Line type="monotone" dataKey="Winnemucca" stroke="var(--color-critical)" strokeWidth={2.5} dot={{ r: 2.5 }} />
            <Line type="monotone" dataKey="Network" stroke="var(--color-chart-1)" strokeDasharray="5 4" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[12px] text-text-muted">
        {LOCUMS.length} rotating clinicians at {Math.min(...LOCUMS.map((l) => l.ratePct))} to {Math.max(...LOCUMS.map((l) => l.ratePct))}%: a protocol gap.
      </p>
    </RainCard>
  );
}

/** Current, projected by December 31 and target, per measure. */
export function MeasureProjection({ points }: { points?: string[] }) {
  const data = MEASURES.map((m) => ({ label: m.id, Current: m.current, 'Projected Dec 31': m.projected, Target: m.target }));
  return (
    <RainCard eyebrow="Projection" title="Each measure by December 31" points={points}>
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-chart-grid)" vertical={false} />
            <XAxis dataKey="label" {...AXIS} />
            <YAxis tickFormatter={(v) => `${v}%`} {...AXIS} width={38} domain={[0, 80]} />
            <Tooltip formatter={(v) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <RBar dataKey="Current" fill="var(--color-chart-6)" radius={[3, 3, 0, 0]} />
            <RBar dataKey="Projected Dec 31" fill="var(--color-chart-1)" radius={[3, 3, 0, 0]} />
            <RBar dataKey="Target" fill="var(--color-chart-2)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[12px] text-text-muted">CMS122 is lower-is-better. BP reaches about 66% with {BP.projected} more controlled.</p>
    </RainCard>
  );
}

/** The campaign ready to approve: counts by mode, cuffs, standing orders. */
export function CampaignPreview({ points }: { points?: string[] }) {
  const { approved } = useRainState();
  const members = getCampaignMembers();
  const cuffs = members.filter((m) => m.cuff === 'Ship first').length;
  return (
    <RainCard eyebrow="BP campaign" title={`${BP.nearControl} members, ranked by likelihood of reaching control`} points={points} aside={<Pill tone={approved.bp412 ? 'good' : 'warning'}>{approved.bp412 ? 'Sent to the Worklist' : 'Awaiting approval'}</Pill>}>
      <div className="grid grid-cols-2 gap-2 @lg:grid-cols-4">
        {[
          { label: 'Members', value: num(BP.nearControl) },
          { label: 'In person', value: num(BP.inPerson) },
          { label: 'Telehealth + cuff', value: num(BP.telehealth) },
          { label: 'Cuffs to ship', value: num(cuffs) },
        ].map((s) => (
          <div key={s.label} className="rounded-xl bg-surface-2/70 px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">{s.label}</p>
            <p className="text-[18px] font-bold tabular-nums text-text">{s.value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3">
        <ResponsiveTable caption="Top five campaign members" columns={memberColumns({ cuff: true })} rows={members.slice(0, 5)} rowKey={(m) => m.id} />
      </div>
      <p className="mt-2 text-[12px] text-text-muted">About {BP.projected} projected to reach control; {BP.needed} clears the gate.</p>
    </RainCard>
  );
}

/** Booked and controlled against the 412 (closed loop from the care team). */
export function CampaignProgress({ points, compact = false }: { points?: string[]; compact?: boolean }) {
  const { campaign } = useRainState();
  const bookedPct = (campaign.booked / BP.nearControl) * 100;
  const ctlPct = (campaign.controlled / BP.nearControl) * 100;
  const bar = (
    <div>
      <Meter
        className="h-3"
        label={`${campaign.booked} of ${BP.nearControl} booked, ${campaign.controlled} controlled`}
        spans={[
          { from: 0, to: bookedPct, className: 'fill-brand/35' },
          { from: 0, to: ctlPct, className: 'fill-success' },
        ]}
      />
      <p className="mt-1 flex flex-wrap justify-between gap-x-3 text-[12px] text-text-muted">
        <span>
          <b className="text-text">{campaign.booked} of {BP.nearControl}</b> booked, <b className="text-success-700">{campaign.controlled}</b> controlled
        </span>
        <span>Goal: {BP.needed} more controlled by December 31</span>
      </p>
    </div>
  );
  if (compact) return bar;
  return (
    <RainCard eyebrow="Campaign progress" title="BP campaign, booked and controlled" points={points}>
      {bar}
      <p className="mt-2 text-[12px] text-text-muted">Controlled readings update the quality gate the same day.</p>
    </RainCard>
  );
}
