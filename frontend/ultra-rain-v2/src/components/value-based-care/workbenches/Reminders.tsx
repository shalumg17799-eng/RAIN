import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, MessageSquareText, PhoneCall, Send } from 'lucide-react';
import { CARE, LINDA, bpText } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import type { ReminderRow } from '@/data/rain/_shared/records';
import { getReminders } from '@/data/rain/_shared/records';
import WorkbenchLayout from '@/components/value-based-care/shell/WorkbenchLayout';
import type { Tone } from '@/components/value-based-care/shell/valueBasedCareKit';
import { Button, Pill, ValueBasedCareCard, ResponsiveTable, Segmented } from '@/components/value-based-care/shell/valueBasedCareKit';
import { LINDA_ID, useRainState } from '@/components/value-based-care/shell/store';
import { usePaneContext } from './useWorkbench';

type View = 'all' | 'unconfirmed' | 'r';

/** What Linda did in her phone view, as it lands in her SMS log. */
const STATUS_TONE: Record<ReminderRow['status'], Tone> = {
  'Change requested (R)': 'critical',
  'Change requested by patient': 'warning',
  'No reply yet': 'warning',
  'Confirmed (C)': 'good',
  'Confirmed by patient': 'good',
  Read: 'info',
  Scheduled: 'neutral',
};

const APPROVED_LOG = {
  mobile: `Switch approved: mobile clinic, Battle Mountain, ${LINDA.mobileClinic.day}, ${LINDA.mobileClinic.date}, ${LINDA.mobileClinic.time}.`,
  ride: `Covered ride approved to Sierra Basin ${LINDA.clinic}; the clinic will call her to set the day.`,
} as const;

const VISIT_LOG = { keep: 'Confirmed her video visit in Ask AI', mobile: 'Asked in Ask AI to switch to the mobile clinic', ride: 'Asked in Ask AI for a covered ride' } as const;

/**
 * Reminders (P2, representative): each patient's reminder plan and SMS log.
 * Patients who reply R get three new slots by SMS; no reply by 24 hours
 * before the visit creates a call task back on Teresa's worklist.
 */
export default function Reminders({ access, filter }: { access: Access; filter: string | null }) {
  const store = useRainState();
  const navigate = useNavigate();
  const [view, setView] = useState<View>(filter === 'unconfirmed' || filter === 'r' ? filter : 'all');
  const [sel, setSel] = useState<string>(LINDA_ID);
  const [sent, setSent] = useState<Record<string, boolean>>({});
  const linda = store.linda;
  const lindaBooked = !!store.bookings[LINDA_ID];
  // Her reminders follow the language she chose in her phone view (English by default).
  const lindaLang = linda.lang === 'es' ? 'Spanish' : 'English';
  const reminder =
    linda.lang === 'es'
      ? `Hola Linda, tiene una cita por video con Sierra Basin ${LINDA.visit.es}. Responda C para confirmar o R para cambiar la cita.`
      : `Hi Linda, you have a video visit with Sierra Basin on ${LINDA.visit.day}, ${LINDA.visit.date} at ${LINDA.visit.time}. Reply C to confirm or R to change it.`;

  const rows: ReminderRow[] = getReminders().map((r) => {
    if (r.memberId !== LINDA_ID) return r;
    const log: ReminderRow['log'] = lindaBooked
      ? [
          { at: 'Today', dir: 'out', text: 'Booking confirmed by Brandon Kee: video visit, Thursday 2:00 PM.' },
          { at: '72 h before', dir: 'out', text: `${reminder} Secure link: ${LINDA.site}` },
          ...(linda.opened ? [{ at: '72 h before', dir: 'in' as const, text: 'Read: opened her secure link' }] : []),
          ...(linda.homeReading ? [{ at: 'Today', dir: 'in' as const, text: `Home reading shared: ${bpText(linda.homeReading)}` }] : []),
          ...(linda.visit ? [{ at: 'Today', dir: 'in' as const, text: VISIT_LOG[linda.visit] }] : []),
          ...(linda.visit && linda.visit !== 'keep' && linda.requestApproved ? [{ at: 'Today', dir: 'out' as const, text: APPROVED_LOG[linda.visit] }] : []),
          ...(linda.afterVisit ? [{ at: 'After the visit', dir: 'out' as const, text: `After-visit summary sent in ${lindaLang}` }] : []),
        ]
      : [{ at: 'Not booked yet', dir: 'out', text: `Plan ready: ${lindaLang} SMS at 72, 24 and 3 hours before the visit.` }];
    const approved = linda.visit !== 'keep' && linda.requestApproved;
    const status: ReminderRow['status'] = !lindaBooked ? 'Scheduled' : linda.visit === 'keep' ? 'Confirmed by patient' : approved ? 'Scheduled' : linda.visit ? 'Change requested by patient' : linda.opened ? 'Read' : 'Scheduled';
    const visit = approved && linda.visit === 'mobile' ? `${LINDA.mobileClinic.day}, ${LINDA.mobileClinic.date}, ${LINDA.mobileClinic.time} · mobile clinic` : r.visit;
    return { ...r, visit, language: lindaLang, status, log };
  });
  const shown = rows.filter((r) => view === 'all' || (view === 'r' ? r.status === 'Change requested (R)' : r.status === 'No reply yet'));
  const row = rows.find((r) => r.memberId === sel) ?? rows[0];
  usePaneContext({ label: `Reminders: ${row.name}`, chips: ['Explain the reminder plan', 'Handle the R replies', 'Show unconfirmed visits for tomorrow'], kind: 'member', id: row.memberId });

  return (
    <WorkbenchLayout meta={WORKBENCHES.reminders} access={access} insights={false}>
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'Unconfirmed tomorrow', value: CARE.brandonUnconfirmed },
          { label: 'Replied R', value: CARE.brandonRReplies },
          { label: 'Call tasks for Teresa', value: CARE.brandonUnconfirmed },
        ].map((t) => (
          <div key={t.label} className="rounded-xl border border-border bg-surface px-3 py-2">
            <p className="text-[11px] font-semibold text-text-muted">{t.label}</p>
            <p className="text-[18px] font-bold tabular-nums text-text">{t.value}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-4 @2xl:grid-cols-[minmax(0,1fr)_minmax(0,300px)]">
        <ValueBasedCareCard
          eyebrow="Reminder plans"
          title="Plans and replies"
          aside={
            <Segmented<View>
              label="Show"
              value={view}
              onChange={setView}
              options={[
                { value: 'all', label: 'All' },
                { value: 'unconfirmed', label: 'No reply' },
                { value: 'r', label: 'Replied R' },
              ]}
            />
          }
        >
          <ResponsiveTable
            caption="Reminder plans"
            rows={shown}
            rowKey={(r) => r.memberId}
            onRowClick={(r) => setSel(r.memberId)}
            selectedKey={row.memberId}
            columns={[
              { key: 'name', label: 'Patient', render: (r) => <span className="font-semibold">{r.name}</span> },
              { key: 'visit', label: 'Visit' },
              { key: 'plan', label: 'Plan', wideOnly: true, render: (r) => <span className="text-[12px] text-text-muted">{r.plan}</span> },
              {
                key: 'status',
                label: 'Status',
                render: (r) => <Pill tone={STATUS_TONE[r.status]}>{r.status}</Pill>,
              },
            ]}
          />
        </ValueBasedCareCard>
        <ValueBasedCareCard eyebrow="SMS log" title={row.name} className="self-start">
          <p className="mb-2 text-[12px] text-text-muted">
            {row.language} · {row.plan}
          </p>
          <ol className="space-y-1.5">
            {row.log.map((l, i) => (
              <li key={i} className={`max-w-[92%] rounded-xl px-2.5 py-1.5 text-[12.5px] ${l.dir === 'out' ? 'bg-surface-2 text-text' : 'ml-auto bg-brand text-white'}`}>
                <span className="block text-[10.5px] opacity-70">{l.at}</span>
                {l.text}
              </li>
            ))}
          </ol>
          <div className="mt-3 flex flex-wrap gap-2">
            {row.status === 'Change requested (R)' &&
              (sent[row.memberId] ? (
                <Pill tone="good">
                  <CheckCircle2 className="h-3 w-3" aria-hidden="true" /> Three new slots sent by SMS
                </Pill>
              ) : (
                <Button variant="primary" disabled={access !== 'full'} onClick={() => setSent({ ...sent, [row.memberId]: true })}>
                  <Send className="h-3.5 w-3.5" aria-hidden="true" /> Send three new slots
                </Button>
              ))}
            {row.status === 'No reply yet' && (
              <Pill tone="warning">
                <PhoneCall className="h-3 w-3" aria-hidden="true" /> Call task on Teresa’s worklist
              </Pill>
            )}
            {row.memberId === LINDA_ID && (
              <Button onClick={() => navigate('/patient')}>
                <MessageSquareText className="h-3.5 w-3.5" aria-hidden="true" /> Open Linda’s phone
              </Button>
            )}
          </div>
        </ValueBasedCareCard>
      </div>
    </WorkbenchLayout>
  );
}
