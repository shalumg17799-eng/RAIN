// @ultra-shell: a tenant route outside the app shell; it reads the session's client and persona. Rule 5 lets the shell read context.
import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, BatteryFull, BookOpen, CalendarCheck2, ChevronLeft, ChevronRight, Copy, Lock, RotateCcw, Share, Signal, Wifi } from 'lucide-react';
import { useBranding } from '@/context/BrandingContext';
import { usePersona } from '@/context/PersonaContext';
import { CARE, LINDA, PATIENT_PERSONA_ID, PERSONAS, bpText } from '@/data/rain/_shared/constants';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import { UI } from '@/data/rain/_shared/patient';
import { DataLabel } from '@/components/value-based-care/shell/valueBasedCareKit';
import type { ValueBasedCareState } from '@/components/value-based-care/shell/store';
import { lindaAfterVisit, lindaOpenLink, lindaSignedIn, markPatientVisit, restartLinda, useRainState } from '@/components/value-based-care/shell/store';
import PatientChat from './PatientChat';

/**
 * Linda Garcia's experience (spec v2.1, Use Case C): Ask AI for patients in
 * her phone's web browser. It starts on her text messages (a secure link from
 * her clinic), shows the one-time code screen for one second, then her
 * conversation. On a laptop the phone is centred on a neutral background; on a
 * phone the page fills the screen. Beside the phone, outside it, the presenter
 * moves the story to Thursday and sees each step land in the care team's
 * workbenches. Renders inside the session but outside the app shell: the
 * patient has no navigation and no workbenches.
 */

function StatusBar() {
  return (
    <div className="flex items-center justify-between bg-surface px-6 pb-1 pt-2.5 text-[13px] font-semibold text-text" aria-hidden="true">
      <span>9:41</span>
      <span className="flex items-center gap-1">
        <Signal className="h-3.5 w-3.5" />
        <Wifi className="h-3.5 w-3.5" />
        <BatteryFull className="h-4 w-4" />
      </span>
    </div>
  );
}

/** Mobile browser chrome: it must read as a website on a phone, not an app. */
function Browser({ children }: { children: ReactNode }) {
  return (
    <>
      <div className="bg-surface-2 px-3 pb-2 pt-1">
        <p className="flex items-center justify-center gap-1.5 rounded-xl bg-surface px-3 py-2 text-[13px] text-text">
          <Lock className="h-3 w-3 text-text-muted" aria-hidden="true" />
          <span className="truncate">{LINDA.site}</span>
        </p>
      </div>
      <div className="min-h-0 flex-1">{children}</div>
      <div className="flex items-center justify-around border-t border-border bg-surface-2 px-4 py-2 text-text-muted" aria-hidden="true">
        <ChevronLeft className="h-5 w-5" />
        <ChevronRight className="h-5 w-5" />
        <Share className="h-5 w-5" />
        <BookOpen className="h-5 w-5" />
        <Copy className="h-5 w-5" />
      </div>
    </>
  );
}

/** Her text messages: the clinic's text with the secure link. */
function Messages({ lang }: { lang: 'en' | 'es' }) {
  const [before, url] = UI.sms[lang].split('https://');
  return (
    <div className="flex h-full flex-col bg-bg" lang={lang}>
      <div className="border-b border-border bg-surface px-4 pb-2 pt-1 text-center">
        <p className="text-[16px] font-bold text-text">Sierra Basin</p>
        <p className="text-[12px] text-text-muted">{UI.textMessage[lang]}</p>
      </div>
      <div className="flex-1 px-3 py-4">
        <p className="max-w-[85%] rounded-2xl rounded-bl-md bg-surface px-3.5 py-2.5 text-[16px] leading-snug text-text shadow-sm">
          {before}
          <button type="button" onClick={lindaOpenLink} className="break-all text-left font-semibold text-brand underline underline-offset-2">
            https://{url}
          </button>
        </p>
        <p className="mt-3 text-center text-[13px] text-text-muted">{UI.smsHint[lang]}</p>
      </div>
    </div>
  );
}

/** The one-time code from her text signs her in; shown for one second. */
function CodeScreen({ lang }: { lang: 'en' | 'es' }) {
  useEffect(() => {
    const t = window.setTimeout(lindaSignedIn, 1000);
    return () => window.clearTimeout(t);
  }, []);
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 bg-bg px-6 text-center" lang={lang} role="status">
      <p className="text-[20px] font-bold text-brand">{UI.brand[lang]}</p>
      <p className="text-[16px] font-semibold text-text">{UI.signingIn[lang]}</p>
      <p className="flex gap-1.5" aria-hidden="true">
        {'482913'.split('').map((d, i) => (
          <span key={i} className="flex h-11 w-9 items-center justify-center rounded-lg border-2 border-brand bg-surface text-[20px] font-bold tabular-nums text-text">
            {d}
          </span>
        ))}
      </p>
      <p className="text-[14px] text-text-muted">{UI.codeNote[lang]}</p>
    </div>
  );
}

/** What each of her steps changed for the care team, with a way into that workbench. */
function careTeamUpdates(s: ValueBasedCareState): Array<{ id: string; text: string; href: string; tone: 'good' | 'warning' | 'critical' }> {
  const l = s.linda;
  const at = (wb: keyof typeof WORKBENCHES, persona: string) => `${WORKBENCHES[wb].path}?persona=${persona}`;
  const out: Array<{ id: string; text: string; href: string; tone: 'good' | 'warning' | 'critical' }> = [];
  if (l.opened) out.push({ id: 'read', text: "Brandon's Reminders: 72-hour reminder read", href: at('reminders', PERSONAS.access), tone: 'good' });
  if (l.homeReading) out.push({ id: 'reading', text: `Teresa's Worklist: New home reading: ${bpText(l.homeReading)}`, href: at('worklist', PERSONAS.chw), tone: 'good' });
  if (l.alert) out.push({ id: 'alert', text: `Teresa's Worklist: high reading alert (${bpText(l.alert)})`, href: at('worklist', PERSONAS.chw), tone: 'critical' });
  if (l.visit)
    out.push({
      id: 'visit',
      text: l.visit === 'keep' ? "Brandon's Scheduling: Confirmed by patient" : `Brandon's Scheduling: ${l.visit === 'mobile' ? 'mobile clinic switch' : 'ride request'} ${l.requestApproved ? 'approved' : 'waiting for approval'}`,
      href: at('scheduling', PERSONAS.access),
      tone: l.visit === 'keep' || l.requestApproved ? 'good' : 'warning',
    });
  if (l.message) out.push({ id: 'message', text: "Teresa's Worklist: asked for a call back", href: at('worklist', PERSONAS.chw), tone: 'warning' });
  if (s.lindaReading) out.push({ id: 'gap', text: `BP gap closed: campaign now ${s.campaign.controlled} controlled (was ${CARE.controlled})`, href: at('qualityGate', PERSONAS.cmo), tone: 'good' });
  return out;
}

const TONE = { good: 'bg-success', warning: 'bg-warning', critical: 'bg-critical' } as const;

export default function PatientView() {
  const { clientId } = useBranding() as unknown as { clientId: string };
  const persona = usePersona() as { id: string } | null;
  const navigate = useNavigate();
  const store = useRainState();
  const { linda } = store;
  useEffect(() => markPatientVisit(), []);
  if (clientId !== 'rain') return <Navigate to="/ask" replace />;

  const isLinda = persona?.id === PATIENT_PERSONA_ID;
  const back = () => {
    if (!isLinda && window.history.length > 1) navigate(-1);
    else navigate(`/ask?persona=${isLinda ? (store.lastOperator ?? PERSONAS.ceo) : persona?.id ?? PERSONAS.ceo}`);
  };
  const updates = careTeamUpdates(store);
  const canJump = linda.visit === 'keep' && !linda.afterVisit;

  return (
    <div className="min-h-dvh overflow-x-hidden bg-surface-2 sm:px-4 sm:py-5">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-5 lg:flex-row lg:items-start lg:justify-center">
        <div className="order-1 w-full sm:max-w-[390px]">
          <div className="flex h-dvh flex-col overflow-hidden bg-surface sm:h-[min(844px,calc(100dvh-2.5rem))] sm:rounded-[44px] sm:border-[10px] sm:border-text sm:shadow-xl">
            <StatusBar />
            {linda.phase === 'sms' ? (
              <div className="min-h-0 flex-1">
                <Messages lang={linda.lang} />
              </div>
            ) : (
              <Browser>{linda.phase === 'code' ? <CodeScreen lang={linda.lang} /> : <PatientChat linda={linda} />}</Browser>
            )}
          </div>
        </div>

        <aside className="order-2 w-full max-w-[390px] px-4 pb-6 sm:px-0 lg:sticky lg:top-5 lg:max-w-xs">
          <button type="button" onClick={back} className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[13px] font-semibold text-brand hover:bg-brand/10">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to RAIN
          </button>
          <h1 className="mt-2 text-lg font-bold text-text">{LINDA.name}’s phone</h1>
          <div className="mt-1.5">
            <DataLabel />
          </div>

          <div className="mt-4 space-y-2">
            <button
              type="button"
              onClick={lindaAfterVisit}
              disabled={!canJump}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand px-3 py-2.5 text-[13.5px] font-semibold text-white disabled:opacity-40"
            >
              <CalendarCheck2 className="h-4 w-4" aria-hidden="true" /> Thursday, after the visit
            </button>
            {!linda.afterVisit && !canJump && <p className="text-[12px] text-text-muted">Available once Linda keeps her Thursday video visit.</p>}
            <button type="button" onClick={restartLinda} className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-border bg-surface px-3 py-2 text-[13px] font-semibold text-text hover:bg-surface-2">
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Start her phone over
            </button>
          </div>

          <h2 className="mt-5 text-[12px] font-bold uppercase tracking-wide text-text-muted">What the care team sees</h2>
          {updates.length === 0 ? (
            <p className="mt-1 text-[12.5px] text-text-muted">Nothing yet.</p>
          ) : (
            <ul className="mt-1.5 space-y-1.5">
              {updates.map((u) => (
                <li key={u.id} className="flex items-start gap-2 rounded-lg bg-surface px-2.5 py-2 text-[12.5px] text-text">
                  <span className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${TONE[u.tone]}`} aria-hidden="true" />
                  <span className="min-w-0 flex-1">{u.text}</span>
                  <Link to={u.href} className="flex-shrink-0 font-semibold text-brand hover:underline">
                    Open
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}
