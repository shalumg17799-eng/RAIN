import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, CalendarPlus, Inbox, MessageSquareText, Phone, Sparkles } from 'lucide-react';
import { BP, CARE, LINDA, MODEL } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import type { CampaignMember, ContactStatus, VisitMode } from '@/data/rain/_shared/records';
import { getCampaignMembers, getTeresaWorklist } from '@/data/rain/_shared/records';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { Button, FilterSelect, GroupLabel, Pill, RainCard, ResponsiveTable } from '../shell/rainKit';
import { clearContact, isReleased, logContact, scheduleMember, useRainState } from '../shell/store';
import { CampaignProgress } from '../cards/quality';
import { usePaneContext } from './useWorkbench';

/** Outcomes logged by hand; "Reached and booked" is set by confirming a booking. */
const OUTCOMES: ContactStatus[] = ['Reached and declined', 'Left message', 'Wrong number'];

/** What to do next, given what happened on the last call. */
function nextStep(status: ContactStatus, loggedToday: boolean, booked: boolean): string {
  if (booked) return 'Visit booked. Reminders go out by text automatically.';
  if (status === 'Reached and declined') return 'Declined, so there is nothing to book. Select the outcome again to clear it.';
  if (status === 'Wrong number') return 'Wrong number. Update it in the EHR before trying again.';
  if (status === 'Left message') return loggedToday ? 'Message left. This patient stays on your call-back list; select the outcome again to clear it.' : 'Called yesterday and left a message. Call again today.';
  return 'If you reach them, book the visit while you are on the call. If not, log what happened.';
}

/**
 * Worklist (P1): the ranked outreach list with reasons (the BP campaign
 * Dr. Castellanos sent), the patient summary drawer, the contact log and
 * campaign progress. The CMO sees it view only.
 */
export default function Worklist({ access, filter }: { access: Access; filter: string | null }) {
  const store = useRainState();
  const navigate = useNavigate();
  const view = access !== 'full';
  const [scope, setScope] = useState(filter === 'teresa46' || !view ? 'teresa' : 'all');
  const [site, setSite] = useState('all');
  const [mode, setMode] = useState<'all' | VisitMode>('all');
  const [contacted, setContacted] = useState<'all' | 'yes' | 'no'>('all');
  const [sel, setSel] = useState<string | null>(view ? null : 'M-40107');

  const base = scope === 'teresa' ? getTeresaWorklist() : getCampaignMembers();
  const status = (m: CampaignMember) => store.contacts[m.id] ?? m.status;
  const rows = base.filter(
    (m) =>
      (site === 'all' || m.siteId === site) &&
      (mode === 'all' || m.mode === mode) &&
      (contacted === 'all' || (contacted === 'yes' ? status(m) !== 'Not contacted' : status(m) === 'Not contacted')),
  );
  const m = getCampaignMembers().find((x) => x.id === sel);
  const isLinda = m?.id === 'M-40107';
  usePaneContext(
    m
      ? {
          label: `${m.name}, rank ${m.rank}${scope === 'teresa' ? ` of your ${CARE.teresaTop}` : ` of ${BP.nearControl}`}`,
          chips: view ? ['Explain this ranking'] : [isLinda ? 'Why is she ranked first?' : 'Why is this patient ranked here?', 'Give me talking points in Spanish for this patient', 'Book a visit for this patient'],
          kind: 'member',
          id: m.id,
        }
      : { label: `Worklist: ${rows.length} patients`, chips: view ? ['Explain this ranking'] : ['Who is closest to BP control?', 'Who has not answered reminders?'] },
  );
  const select = (id: string) => {
    setSel(id);
    if (!view) scheduleMember(id);
  };
  const pendingFix = (store.fixPreview || store.cosignRequested) && !isReleased(store);

  return (
    <WorkbenchLayout meta={WORKBENCHES.worklist} access={access} insights={false}>
      <div className="space-y-2">
        <p className="flex items-start gap-2 rounded-xl bg-brand/[0.06] px-3 py-2 text-[12.5px] text-text">
          <Inbox className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand" aria-hidden="true" />
          From Dr. Castellanos: BP campaign, {BP.nearControl} patients; {CARE.teresaTop} top priority at your sites this week.
        </p>
        {store.approved.outreach300 && (
          <p className="flex items-start gap-2 rounded-xl bg-brand/[0.06] px-3 py-2 text-[12.5px] text-text">
            <Sparkles className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand" aria-hidden="true" />
            From Gregory Haskins: top 300 outreach worklist, queued after the BP campaign.
          </p>
        )}
        {pendingFix && (
          <p role="status" className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning-subtle px-3 py-2 text-[12.5px] text-warning-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
            Ranking update pending sign-off: {MODEL.missingFromTop} high-need frontier members will join the top 300. Keep working the current list.
          </p>
        )}
        {isReleased(store) && <p className="rounded-xl border border-success/30 bg-success-subtle px-3 py-2 text-[12.5px] text-success-700">Access-adjusted ranking {MODEL.candidate} released by the CIO and CMO.</p>}
      </div>
      <RainCard eyebrow="Campaign progress" title="BP campaign">
        <CampaignProgress compact />
      </RainCard>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <FilterSelect label="List" value={scope} onChange={(v) => { setScope(v); setSel(null); }} options={[{ value: 'teresa', label: `Top priority (${CARE.teresaTop})` }, { value: 'all', label: `Whole campaign (${BP.nearControl})` }]} />
        <FilterSelect label="Site" value={site} onChange={setSite} options={[{ value: 'all', label: 'All sites' }, { value: 'winnemucca', label: 'Winnemucca' }, { value: 'battleMountain', label: 'Battle Mountain' }]} />
        <FilterSelect label="Visit mode" value={mode} onChange={(v) => setMode(v as 'all' | VisitMode)} options={[{ value: 'all', label: 'All modes' }, { value: 'Telehealth', label: 'Telehealth' }, { value: 'In person', label: 'In person' }]} />
        <FilterSelect label="Contacted" value={contacted} onChange={(v) => setContacted(v as 'all' | 'yes' | 'no')} options={[{ value: 'all', label: 'All' }, { value: 'no', label: 'Not contacted' }, { value: 'yes', label: 'Contacted' }]} />
      </div>
      <div className="grid gap-4 @2xl:grid-cols-[minmax(0,1fr)_minmax(0,300px)]">
        <div className={`min-w-0 ${m ? 'order-2 @2xl:order-none' : ''}`}>
          <ResponsiveTable
            caption="Ranked outreach list"
            rows={rows.slice(0, 60)}
            rowKey={(r) => r.id}
            onRowClick={(r) => select(r.id)}
            selectedKey={sel}
            highlight={store.highlight}
            empty="No patients match these filters."
            columns={[
              { key: 'rank', label: '#', align: 'right', render: (r) => r.rank },
              { key: 'name', label: 'Patient', render: (r) => <span className="font-semibold">{r.name}</span> },
              { key: 'reasons', label: 'Top 3 reasons', render: (r) => <span className="text-[12px] text-text-muted">{r.reasons.join(' · ')}</span> },
              { key: 'mode', label: 'Visit mode', render: (r) => <Pill tone={r.mode === 'Telehealth' ? 'brand' : 'neutral'}>{r.mode}</Pill> },
              { key: 'last', label: 'Last contact', render: (r) => <span className="text-[12px]">{store.contacts[r.id] ?? r.lastContact}</span> },
            ]}
          />
          {rows.length > 60 && <p className="mt-2 text-[12px] text-text-muted">Showing the first 60 of {rows.length}.</p>}
        </div>
        {m && (
          <RainCard eyebrow={`Rank ${m.rank} · patient summary`} title={m.name} className={`order-1 self-start @2xl:order-none @2xl:sticky @2xl:top-0`}>
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-[12.5px]">
              <dt className="text-text-subtle">Conditions</dt>
              <dd>{m.conditions.join(', ')}</dd>
              <dt className="text-text-subtle">Open gaps</dt>
              <dd>BP control (CMS165){m.conditions.includes('Type 2 diabetes') ? ', HbA1c' : ''}</dd>
              <dt className="text-text-subtle">Last reading</dt>
              <dd>
                BP {m.lastBp} in {m.lastBpMonth}
              </dd>
              <dt className="text-text-subtle">Social needs</dt>
              <dd>{m.socialNeeds.length ? m.socialNeeds.join(', ') : 'None flagged'}</dd>
              <dt className="text-text-subtle">Language</dt>
              <dd>
                {m.language} · {m.channel}
              </dd>
              <dt className="text-text-subtle">History</dt>
              <dd>{isLinda ? `Missed ${LINDA.missedVisits} visits; answers texts in Spanish` : m.lastContact === 'Yesterday, left message' ? 'Called yesterday, left a message' : 'No contact yet this campaign'}</dd>
              <dt className="text-text-subtle">Drive</dt>
              <dd>{m.driveMin} minutes</dd>
            </dl>
            <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-brand/[0.06] px-2.5 py-1.5 text-[12.5px] text-text">
              <Sparkles className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-brand" aria-hidden="true" />
              Ask AI suggests: {m.mode === 'Telehealth' ? `Telehealth recheck with home cuff; ${m.cuff === 'Ship first' ? 'ship a cuff first' : 'cuff on file'}.` : 'In-person recheck at the nearest site.'}
            </p>
            <GroupLabel className="mt-3">Call</GroupLabel>
            <div className="rounded-lg border border-border px-2.5 py-2 text-[12.5px]">
              <p className="flex items-center gap-1.5 font-semibold tabular-nums text-text">
                <Phone className="h-3.5 w-3.5 text-brand" aria-hidden="true" /> {m.phone}
              </p>
              <p className="mt-0.5 text-[12px] text-text-muted">
                Best time: {m.bestTime}
                {m.phoneNote ? `. ${m.phoneNote}.` : ''}
              </p>
            </div>
            <GroupLabel className="mt-3">After the call</GroupLabel>
            <p className="mb-2 text-[12px] text-text-muted">{nextStep(status(m), !!store.contacts[m.id], !!store.bookings[m.id])}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                disabled={view || !!store.bookings[m.id] || !!store.contacts[m.id]}
                onClick={() => { scheduleMember(m.id); navigate('/scheduling?filter=selected'); }}
              >
                <CalendarPlus className="h-3.5 w-3.5" aria-hidden="true" /> {store.bookings[m.id] ? 'Booked' : 'Book visit'}
              </Button>
              {isLinda && (
                <Button onClick={() => navigate('/patient')}>
                  <MessageSquareText className="h-3.5 w-3.5" aria-hidden="true" /> Patient texts
                </Button>
              )}
            </div>
            {!store.bookings[m.id] && (
              <>
                <p className="mb-1.5 mt-3 text-[12px] font-semibold text-text-muted">Could not book? Log what happened:</p>
                <div className="grid grid-cols-2 gap-1.5">
                  {OUTCOMES.map((o) => (
                    <button
                      key={o}
                      type="button"
                      disabled={view}
                      aria-pressed={store.contacts[m.id] === o}
                      onClick={() => (store.contacts[m.id] === o ? clearContact(m.id) : logContact(m.id, o))}
                      className={`rounded-lg border px-2 py-1.5 text-left text-[12px] font-semibold disabled:opacity-50 ${store.contacts[m.id] === o ? 'border-brand bg-brand/10 text-brand' : 'border-border text-text hover:bg-surface-2'}`}
                    >
                      {o}
                    </button>
                  ))}
                </div>
              </>
            )}
          </RainCard>
        )}
      </div>
    </WorkbenchLayout>
  );
}
