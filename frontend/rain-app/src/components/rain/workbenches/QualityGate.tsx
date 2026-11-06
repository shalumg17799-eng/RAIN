import { useMemo, useState } from 'react';
import { CheckCircle2, Send } from 'lucide-react';
import { BP, CODING, MEASURES, isMet, num } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import type { CampaignMember, VisitMode } from '@/data/rain/_shared/records';
import { getCampaignMembers } from '@/data/rain/_shared/records';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { Button, Pill, RainCard, ResponsiveTable, Segmented } from '../shell/rainKit';
import { approve, useRainState } from '../shell/store';
import { QualityTracker } from '../cards/insight';
import { CampaignProgress, MeasureProjection } from '../cards/quality';
import { memberColumns } from '../cards/columns';
import { usePaneContext } from './useWorkbench';

const PAGE = 25;

/**
 * Quality Gate and Campaigns (P1): the five-measure tracker, the members
 * behind each gap, and the campaign builder with a visit mode per member and
 * standing orders. The CMO approves and sends; the CEO sees it view only.
 */
export default function QualityGate({ access, filter }: { access: Access; filter: string | null }) {
  const store = useRainState();
  const all = getCampaignMembers();
  const [measure, setMeasure] = useState<string>(filter === 'gate' ? 'CMS165' : 'CMS165');
  const [mode, setMode] = useState<'all' | VisitMode>('all');
  const [shown, setShown] = useState(PAGE);
  const [selected, setSelected] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, VisitMode>>({});
  const view = access !== 'full';
  const sent = !!store.approved.bp412;

  const rows = useMemo(() => all.filter((m) => mode === 'all' || (overrides[m.id] ?? m.mode) === mode), [all, mode, overrides]);
  const member = all.find((m) => m.id === selected);
  usePaneContext(
    member
      ? { label: `${member.name}, rank ${member.rank} of ${BP.nearControl}`, chips: view ? ['Explain this ranking'] : ['Explain this ranking', 'Approve and send to the Worklist'], kind: 'member', id: member.id }
      : measure !== 'CMS165'
        ? { label: `${measure}: ${MEASURES.find((m) => m.id === measure)!.name}`, chips: ['Explain this measure'], kind: 'measure', id: measure }
        : { label: `BP campaign, ${BP.nearControl} members`, chips: view ? ['Explain this measure'] : ['Explain this ranking', 'Approve and send to the Worklist'], kind: 'measure', id: 'CMS165' },
  );

  const columns = [
    ...memberColumns({ cuff: true, orders: true }),
    {
      key: 'mode-edit',
      label: 'Set mode',
      wideOnly: true,
      render: (m: CampaignMember) => (
        <select
          aria-label={`Visit mode for ${m.name}`}
          disabled={view || sent}
          value={overrides[m.id] ?? m.mode}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setOverrides({ ...overrides, [m.id]: e.target.value as VisitMode })}
          className="min-h-[30px] rounded-md border border-border bg-surface px-1.5 text-[12px]"
        >
          <option>Telehealth</option>
          <option>In person</option>
        </select>
      ),
    },
  ];

  const selectedMeasure = MEASURES.find((m) => m.id === measure)!;
  return (
    <WorkbenchLayout
      meta={WORKBENCHES.qualityGate}
      access={access}
      actions={
        sent ? (
          <Pill tone="good">
            <CheckCircle2 className="h-3 w-3" aria-hidden="true" /> Sent to the Worklist
          </Pill>
        ) : (
          <Button variant="primary" disabled={view} title={view ? 'View only: the CMO approves' : undefined} onClick={() => approve('bp412')}>
            <Send className="h-3.5 w-3.5" aria-hidden="true" /> Approve and send to the Worklist
          </Button>
        )
      }
    >
      {view && <p className="rounded-xl border border-border bg-surface-2/60 px-3 py-2 text-[12.5px] text-text-muted">View only. Dr. Castellanos approves campaigns and standing orders.</p>}
      <div className="grid gap-4 @4xl:grid-cols-2">
        <QualityTracker projected selected={measure} onSelect={(id) => { setMeasure(id); setSelected(null); }} />
        <MeasureProjection />
      </div>
      <RainCard eyebrow="Members per gap" title={`${selectedMeasure.name} (${selectedMeasure.id})`} aside={<Pill tone={isMet(selectedMeasure) ? 'good' : 'critical'}>{isMet(selectedMeasure) ? 'Met' : 'Not met'}</Pill>}>
        {measure === 'CMS165' ? (
          <p className="text-[13px] text-text">
            {num(BP.hypertensive)} hypertensive members; {num(BP.nearControl)} had a last reading within {BP.withinPoints} points of control. About {BP.needed} more controlled readings pass the gate; about {BP.projected} are projected with the campaign below.
          </p>
        ) : (
          <p className="text-[13px] text-text">
            {selectedMeasure.current}% now, target {selectedMeasure.higherIsBetter ? `${selectedMeasure.target}% or higher` : `${selectedMeasure.target}% or lower`}, projected {selectedMeasure.projected}% by December 31. {selectedMeasure.id === 'CMS130' ? 'A mailed FIT kit campaign adds about 4 points; it starts now and counts toward next year.' : selectedMeasure.id === 'CMS122' ? 'Planned for Q1: two readings and a medication cycle do not fit in 58 days.' : 'Met: keep the current workflow.'}
          </p>
        )}
        {store.approved.coding73 && (
          <p className="mt-2 rounded-lg bg-brand/[0.06] px-3 py-2 text-[12.5px] text-text">
            Received from Gregory Haskins: coding recapture list, {CODING.members} high-need members, for their next visit or a telehealth review.
          </p>
        )}
      </RainCard>
      <RainCard
        eyebrow="Campaign builder"
        title={`BP campaign: ${BP.nearControl} members ranked by likelihood of reaching control`}
        aside={
          <Segmented<'all' | VisitMode>
            label="Visit mode"
            value={mode}
            onChange={(v) => { setMode(v); setShown(PAGE); }}
            options={[
              { value: 'all', label: `All ${BP.nearControl}` },
              { value: 'In person', label: `In person ${BP.inPerson}` },
              { value: 'Telehealth', label: `Telehealth ${BP.telehealth}` },
            ]}
          />
        }
      >
        <p className="mb-2 text-[12px] text-text-muted">
          Select a member to explain the ranking in Ask AI. {BP.cuffsToShip} telehealth members need a cuff shipped first.
        </p>
        <ResponsiveTable caption="Campaign members" columns={columns} rows={rows.slice(0, shown)} rowKey={(m) => m.id} onRowClick={(m) => setSelected(m.id)} selectedKey={selected} highlight={store.highlight} />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[12px] text-text-muted">
          <span>
            Showing {Math.min(shown, rows.length)} of {rows.length}
          </span>
          {shown < rows.length && <Button onClick={() => setShown(shown + PAGE)}>Show {Math.min(PAGE, rows.length - shown)} more</Button>}
        </div>
      </RainCard>
      <RainCard eyebrow="Closed loop" title="Progress from the care team">
        <CampaignProgress compact />
        <p className="mt-2 text-[12px] text-text-muted">From the Worklist, Scheduling and home cuffs; counts toward CMS165 the same day.</p>
      </RainCard>
    </WorkbenchLayout>
  );
}
