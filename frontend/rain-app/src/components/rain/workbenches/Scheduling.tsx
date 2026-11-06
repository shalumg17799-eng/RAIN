import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, BellRing, CheckCircle2, MessageSquareText, Phone, ShieldCheck, Sparkles } from 'lucide-react';
import { CARE, LINDA } from '@/data/rain/_shared/constants';
import type { Access } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import type { Slot } from '@/data/rain/_shared/records';
import { getMember, getPendingBookings, getSlots } from '@/data/rain/_shared/records';
import { modeReason, reminderPlan } from '@/data/rain/_shared/context';
import WorkbenchLayout from '../shell/WorkbenchLayout';
import { Button, Pill, RainCard, ResponsiveTable, Segmented } from '../shell/rainKit';
import { book, useRainState } from '../shell/store';
import { usePaneContext } from './useWorkbench';

type ModeFilter = 'all' | 'Telehealth (video)' | 'Mobile clinic' | 'In person';

/**
 * Scheduling (P1): slot search by drive time and visit mode, the eligibility
 * check (a mock X12 270/271 behind the scenes), the reminder plan, and booking.
 * Arrives with the first pre-filled booking from Teresa's worklist.
 */
export default function Scheduling({ access, filter }: { access: Access; filter: string | null }) {
  const store = useRainState();
  const navigate = useNavigate();
  const pending = getPendingBookings();
  const firstId = filter === 'selected' && store.scheduleFor ? store.scheduleFor : pending[0].memberId;
  const [memberId, setMemberId] = useState(firstId);
  const [mode, setMode] = useState<ModeFilter>('all');
  const [slotId, setSlotId] = useState<string | null>(null);
  const member = getMember(memberId) ?? getMember(pending[0].memberId)!;
  const booking = pending.find((b) => b.memberId === member.id);
  const lapsed = booking?.eligibility === 'Lapsed';
  const booked = store.bookings[member.id];
  const isLinda = member.id === 'M-40107';

  // Linda's slots as listed; anyone else's in-person drive is their own.
  const slots: Slot[] = getSlots().map((s) => (s.mode === 'In person' ? { ...s, driveMin: member.driveMin } : s.mode === 'Mobile clinic' && !isLinda ? { ...s, where: `Mobile clinic, ${member.site}` } : s));
  const sorted = slots.filter((s) => mode === 'all' || s.mode === mode).sort((a, b) => a.driveMin - b.driveMin);
  const slot = slots.find((s) => s.id === (slotId ?? (member.mode === 'Telehealth' ? 'S1' : null)));

  usePaneContext({
    label: `Booking: ${member.name}, ${member.mode === 'Telehealth' ? 'telehealth recheck' : 'in-person recheck'}`,
    chips: [member.mode === 'Telehealth' ? 'Why telehealth for this patient?' : 'Why this visit mode?', member.driveMin === LINDA.driveMin ? 'What other slots work for an 81-minute drive?' : 'What other slots work for this drive?', 'Explain the reminder plan'],
    kind: 'booking',
    id: member.id,
  });

  const { early, because } = reminderPlan(member);
  const timing = early ? '72 hours, 24 hours and 3 hours before' : '24 hours and 3 hours before';
  return (
    <WorkbenchLayout meta={WORKBENCHES.scheduling} access={access} insights={false}>
      <div className="grid gap-4 @2xl:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
        <RainCard eyebrow="From Teresa's worklist" title={`${CARE.brandonBookings} bookings waiting`} className="self-start">
          <p className="mb-2 text-[12px] text-text-muted">Select a patient to book.</p>
          <ul className="max-h-[200px] space-y-1 overflow-y-auto pr-1 @2xl:max-h-[520px]">
            {pending.map((b) => (
              <li key={b.memberId}>
                <button
                  type="button"
                  onClick={() => { setMemberId(b.memberId); setSlotId(null); }}
                  aria-pressed={b.memberId === member.id}
                  className={`flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-[12.5px] ${b.memberId === member.id ? 'bg-brand/10 font-semibold text-brand' : 'text-text hover:bg-surface-2'}`}
                >
                  <span className="min-w-0 truncate">{b.name}</span>
                  {store.bookings[b.memberId] ? <Pill tone="good">Booked</Pill> : b.eligibility === 'Lapsed' ? <Pill tone="warning">Lapsed</Pill> : <span className="text-[11px] text-text-subtle">{b.mode}</span>}
                </button>
              </li>
            ))}
          </ul>
        </RainCard>
        <div className="min-w-0 space-y-4">
          <RainCard eyebrow="1. Choose a slot" title={`${member.name} · ${member.driveMin}-minute drive · prefers ${member.language}`}>
            <p className="mb-2 flex flex-wrap items-center gap-x-1.5 text-[12px] text-text-muted">
              <Phone className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
              <span className="font-semibold tabular-nums text-text">{member.phone}</span>
              <span>· Best time: {member.bestTime}{member.phoneNote ? ` · ${member.phoneNote}` : ''}</span>
            </p>
            <p className="mb-2 flex items-start gap-1.5 rounded-lg bg-brand/[0.06] px-2.5 py-1.5 text-[12.5px] text-text">
              <Sparkles className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-brand" aria-hidden="true" />
              {modeReason(member)}
            </p>
            {!booked && <p className="mb-2 text-[12px] text-text-muted">Select a slot. The shortest drive is listed first.</p>}
            <div className="mb-2">
              <Segmented<ModeFilter>
                label="Visit mode"
                value={mode}
                onChange={setMode}
                options={[
                  { value: 'all', label: 'All' },
                  { value: 'Telehealth (video)', label: 'Telehealth' },
                  { value: 'Mobile clinic', label: 'Mobile' },
                  { value: 'In person', label: 'In person' },
                ]}
              />
            </div>
            <ResponsiveTable
              caption="Open slots sorted by drive time"
              rows={sorted}
              rowKey={(s) => s.id}
              onRowClick={(s) => !booked && setSlotId(s.id)}
              selectedKey={slot?.id ?? null}
              columns={[
                { key: 'mode', label: 'Mode', render: (s) => <Pill tone={s.mode === 'Telehealth (video)' ? 'brand' : 'neutral'}>{s.mode}</Pill> },
                { key: 'where', label: 'Where' },
                { key: 'provider', label: 'Provider', wideOnly: true },
                { key: 'when', label: 'When', render: (s) => `${s.day}, ${s.time}` },
                { key: 'drive', label: 'Drive', align: 'right', render: (s) => (s.driveMin ? `${s.driveMin} min` : 'None') },
              ]}
            />
          </RainCard>
          {!slot && <p className="rounded-xl border border-dashed border-border px-3 py-2 text-[12.5px] text-text-muted">Select a slot to check coverage and confirm the booking.</p>}
          {slot && (
            <RainCard eyebrow="2. Check coverage" title="High Desert Health Plan">
              {lapsed ? (
                <p className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning-subtle px-3 py-2 text-[12.5px] text-warning-700">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
                  Coverage lapsed with High Desert Health Plan. An enrollment-assist task was created; the booking can still go ahead.
                </p>
              ) : (
                <p className="flex items-start gap-2 rounded-lg border border-success/30 bg-success-subtle px-3 py-2 text-[12.5px] text-success-700">
                  <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
                  Active with High Desert Health Plan. Visit type eligible for {slot.mode === 'Telehealth (video)' ? 'telehealth' : 'an in-person visit'}.
                </p>
              )}
            </RainCard>
          )}
          {slot && (
            <RainCard eyebrow="3. Review and confirm" title="Reminder plan for this visit">
              <p className="mb-2 text-[12px] text-text-muted">Check the details, then confirm. Nothing is sent to the patient until you do.</p>
              <ul className="grid gap-x-4 gap-y-1 text-[12.5px] @lg:grid-cols-2">
                <li>
                  <b>Channel:</b> {member.channel === 'Voice' ? 'Voice call' : 'SMS'}
                </li>
                <li>
                  <b>Language:</b> {member.language}
                </li>
                <li className="@lg:col-span-2">
                  <b>Timing:</b> {timing}
                  {early ? `, because of ${because}` : ''}
                </li>
                <li className="@lg:col-span-2">
                  <b>Quiet hours:</b> no texts 8 PM to 8 AM
                </li>
              </ul>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {booked ? (
                  <Pill tone="good">
                    <CheckCircle2 className="h-3 w-3" aria-hidden="true" /> Booked {slot.day}, {slot.time}
                  </Pill>
                ) : (
                  <Button variant="primary" disabled={access !== 'full'} onClick={() => book(member.id, slot.id)}>
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> Confirm booking
                  </Button>
                )}
                <Button onClick={() => navigate('/reminders')}>
                  <BellRing className="h-3.5 w-3.5" aria-hidden="true" /> Reminders
                </Button>
                {isLinda && (
                  <Button onClick={() => navigate('/patient')}>
                    <MessageSquareText className="h-3.5 w-3.5" aria-hidden="true" /> Patient texts
                  </Button>
                )}
              </div>
            </RainCard>
          )}
        </div>
      </div>
    </WorkbenchLayout>
  );
}
