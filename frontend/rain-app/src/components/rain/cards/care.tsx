/**
 * Use Case B visuals (Teresa and Brandon): the task briefing that lands them
 * on today's work and the button into their main workbench.
 */
import { useNavigate } from 'react-router-dom';
import { ArrowRight, MessageSquare, PhoneCall, Sparkles } from 'lucide-react';
import { CARE, LINDA } from '@/data/rain/_shared/constants';
import { getTeresaWorklist } from '@/data/rain/_shared/records';
import { Button, RainCard } from '../shell/rainKit';
import { useRainState } from '../shell/store';
import { CampaignProgress } from './quality';

/** Today's work for the care team (no insights, no capability tags). */
export function TaskBriefing({ role }: { role: 'chw' | 'access' }) {
  const navigate = useNavigate();
  const { approved } = useRainState();
  if (role === 'chw') {
    const list = getTeresaWorklist();
    return (
      <RainCard eyebrow="Today's queue" title={`${CARE.teresaTop} top-priority patients at Winnemucca and Battle Mountain`}>
        <ul className="space-y-2">
          <li className="flex items-start gap-2 text-[13px]">
            <PhoneCall className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand" aria-hidden="true" />
            <span>
              <b>Start with {list[0].name}:</b> {list[0].reasons.join(', ')}.
            </span>
          </li>
          <li className="flex items-start gap-2 text-[13px]">
            <MessageSquare className="mt-0.5 h-4 w-4 flex-shrink-0 text-warning-700" aria-hidden="true" />
            <span>
              <b>Needs attention:</b> {CARE.teresaNoCallback} patients you called yesterday have not called back.
            </span>
          </li>
          {approved.outreach300 && (
            <li className="flex items-start gap-2 text-[13px]">
              <Sparkles className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand" aria-hidden="true" />
              <span>
                <b>New from Gregory Haskins:</b> outreach worklist for the top 300 impactable members.
              </span>
            </li>
          )}
        </ul>
        <div className="mt-3">
          <CampaignProgress compact />
        </div>
        <div className="mt-3">
          <Button variant="primary" onClick={() => navigate('/worklist?filter=teresa46')}>
            Open my worklist <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        </div>
      </RainCard>
    );
  }
  return (
    <RainCard eyebrow="Today's queue" title="Bookings, confirmations and replies">
      <ul className="grid gap-2 @lg:grid-cols-3">
        {[
          { n: CARE.brandonBookings, label: 'bookings waiting from Teresa’s worklist', tone: 'warning' as const },
          { n: CARE.brandonUnconfirmed, label: 'visits tomorrow still unconfirmed', tone: 'warning' as const },
          { n: CARE.brandonRReplies, label: 'patients replied R and need new slots', tone: 'critical' as const },
        ].map((t) => (
          <li key={t.label} className="rounded-xl bg-surface-2/70 px-3 py-2">
            <p className="text-[20px] font-bold tabular-nums text-text">{t.n}</p>
            <p className="text-[12px] text-text-muted">{t.label}</p>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[13px]">
        <b>First booking:</b> {LINDA.name}, telehealth BP recheck ({LINDA.driveMin}-minute drive, prefers {LINDA.language}).
      </p>
      <div className="mt-3">
        <Button variant="primary" onClick={() => navigate('/scheduling?filter=next')}>
          Start bookings <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      </div>
    </RainCard>
  );
}


