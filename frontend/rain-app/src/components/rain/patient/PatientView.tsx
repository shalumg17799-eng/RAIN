// @ultra-shell: a tenant route outside the app shell; it reads the session's client. Rule 5 lets the shell read context.
import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, Signal, Wifi } from 'lucide-react';
import { useBranding } from '@/context/BrandingContext';
import { LINDA } from '@/data/rain/_shared/constants';
import { markPatientVisit, recordLindaReading, useRainState } from '../shell/store';
import { DataLabel } from '../shell/rainKit';

/**
 * The patient view (spec "Patient view (/patient)"): Linda Garcia's SMS
 * thread in a 390-pixel phone frame, Spanish by default with an English
 * toggle for reviewers, in four screens. The patient does not use Cockpit,
 * so this renders inside the session but outside the app shell. Plain words,
 * short sentences, first name, date, time and clinic only; no clinical advice
 * by text. Her post-visit reading closes her BP gap, which moves Teresa's
 * progress bar and the quality gate tracker.
 */

type Lang = 'es' | 'en';
interface Msg {
  dir: 'in' | 'out';
  es: string;
  en: string;
}

const LINK = 'sierrabasin.example/v/4821';

const SCREENS: Array<{ title: { es: string; en: string }; note: string; msgs: Msg[] }> = [
  {
    title: { es: 'Recordatorio 72 horas', en: '72-hour reminder' },
    note: 'Plain language: first name, date, time and clinic only.',
    msgs: [{ dir: 'out', es: `Hola Linda, tiene una cita por video con Sierra Basin ${LINDA.visit.es}. Responda C para confirmar o R para cambiar la cita.`, en: 'Hi Linda, you have a video visit with Sierra Basin on Thursday, Nov 5 at 2:00 PM. Reply C to confirm or R to change it.' }],
  },
  {
    title: { es: 'Respuesta C', en: 'C reply and confirmation' },
    note: 'Confirmation with the video link and a one-line checklist.',
    msgs: [
      { dir: 'in', es: 'C', en: 'C' },
      { dir: 'out', es: `Gracias, Linda. Su cita está confirmada. Su enlace de video: ${LINK}. Tenga a mano su monitor de presión.`, en: `Thank you, Linda. Your visit is confirmed. Your video link: ${LINK}. Have your blood pressure monitor ready.` },
    ],
  },
  {
    title: { es: 'Día de la cita', en: 'Day-of reminder' },
    note: 'Link resent. A clinical question goes to the front desk; texts give no clinical advice.',
    msgs: [
      { dir: 'out', es: `Linda, su cita por video es hoy a las 2:00 PM. Entre aquí: ${LINK}`, en: `Linda, your video visit is today at 2:00 PM. Join here: ${LINK}` },
      { dir: 'in', es: '¿Tomo mi pastilla antes de la cita?', en: 'Do I take my pill before the visit?' },
      { dir: 'out', es: 'Gracias por preguntar. La recepción le va a llamar pronto. Por texto no damos consejos médicos.', en: 'Thanks for asking. The front desk will call you soon. We do not give medical advice by text.' },
    ],
  },
  {
    title: { es: 'Después de la cita', en: 'After the visit' },
    note: 'Her home cuff reading closes her BP gap: it shows on Teresa’s progress bar and Dr. Castellanos’s quality tracker.',
    msgs: [
      { dir: 'in', es: `Mi presión hoy: ${LINDA.reading}`, en: `My blood pressure today: ${LINDA.reading}` },
      { dir: 'out', es: `Gracias, Linda. Recibimos su lectura: ${LINDA.reading}. Su próxima cita es en 3 meses. Le mandamos un recordatorio.`, en: `Thank you, Linda. We got your reading: ${LINDA.reading}. Your next visit is in 3 months. We will send you a reminder.` },
    ],
  },
];

export default function PatientView() {
  const { clientId } = useBranding() as unknown as { clientId: string };
  const navigate = useNavigate();
  const { lindaReading, campaign } = useRainState();
  const [lang, setLang] = useState<Lang>('es');
  const [step, setStep] = useState(0);
  // Reaching the last screen records her reading: the closed loop back to Use Case A.
  useEffect(() => markPatientVisit(), []);
  useEffect(() => {
    if (step === SCREENS.length - 1) recordLindaReading();
  }, [step]);
  if (clientId !== 'rain') return <Navigate to="/ask" replace />;
  const shown = SCREENS.slice(0, step + 1).flatMap((s, i) => s.msgs.map((m, j) => ({ ...m, key: `${i}-${j}`, current: i === step })));

  return (
    <div className="min-h-screen overflow-x-hidden bg-surface-2 px-4 py-5">
      <div className="mx-auto mb-3 max-w-5xl">
        <button type="button" onClick={() => navigate(-1)} className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[13px] font-semibold text-brand hover:bg-brand/10">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to RAIN
        </button>
      </div>
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-6 lg:flex-row lg:items-start lg:justify-center">
        <aside className="order-2 w-full max-w-[390px] lg:max-w-sm">
          <h1 className="text-lg font-bold text-text">Patient view</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            {LINDA.name}, {LINDA.age}, {LINDA.town}. {LINDA.driveMin}-minute drive, shared family phone, prefers Spanish, broadband at home. SMS first, no app; voice call fallback.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Language" className="inline-flex rounded-lg border border-border bg-surface p-0.5">
              {(['es', 'en'] as Lang[]).map((l) => (
                <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)} className={`rounded-md px-3 py-1 text-[12.5px] font-semibold ${lang === l ? 'bg-brand text-white' : 'text-text-muted hover:text-text'}`}>
                  {l === 'es' ? 'Español' : 'English'}
                </button>
              ))}
            </div>
            <DataLabel />
          </div>
          <ol className="mt-4 space-y-1.5">
            {SCREENS.map((s, i) => (
              <li key={s.title.en}>
                <button
                  type="button"
                  onClick={() => setStep(i)}
                  aria-current={step === i ? 'step' : undefined}
                  className={`w-full rounded-xl border px-3 py-2 text-left ${step === i ? 'border-brand bg-surface shadow-sm' : 'border-transparent hover:bg-surface'}`}
                >
                  <span className="text-[11px] font-bold uppercase tracking-wide text-brand">Screen {i + 1}</span>
                  <span className="block text-[13px] font-semibold text-text">{s.title.en}</span>
                  {step === i && <span className="mt-0.5 block text-[12px] text-text-muted">{s.note}</span>}
                </button>
              </li>
            ))}
          </ol>
          {lindaReading && (
            <p role="status" className="mt-3 rounded-xl border border-success/30 bg-success-subtle px-3 py-2 text-[12.5px] text-success-700">
              Reading {LINDA.reading} received: BP gap closed. Campaign now {campaign.controlled} controlled.
            </p>
          )}
        </aside>

        <div className="order-1 w-full max-w-[390px]">
          <div className="overflow-hidden rounded-[36px] border-[10px] border-text bg-surface shadow-xl">
            <div className="flex items-center justify-between bg-surface px-5 pb-1 pt-2 text-[11px] font-semibold text-text">
              <span>2:00</span>
              <span className="flex items-center gap-1">
                <Signal className="h-3 w-3" aria-hidden="true" />
                <Wifi className="h-3 w-3" aria-hidden="true" />
              </span>
            </div>
            <div className="border-b border-border-subtle bg-surface px-4 pb-2 text-center">
              <p className="text-[13px] font-bold text-text">Sierra Basin</p>
              <p className="text-[11px] text-text-subtle">{lang === 'es' ? 'Mensaje de texto' : 'Text message'}</p>
            </div>
            <ol className="flex min-h-[420px] flex-col gap-2 bg-surface-2/60 px-3 py-4" aria-live="polite" lang={lang}>
              {shown.map((m) => (
                <li
                  key={m.key}
                  className={`max-w-[80%] rounded-2xl px-3 py-2 text-[14px] leading-snug ${m.dir === 'out' ? 'self-start rounded-bl-md bg-surface text-text shadow-sm' : 'self-end rounded-br-md bg-brand text-white'} ${m.current ? '' : 'opacity-60'}`}
                >
                  {lang === 'es' ? m.es : m.en}
                </li>
              ))}
            </ol>
            <div className="flex items-center gap-2 border-t border-border-subtle bg-surface px-3 py-2.5">
              <span className="flex-1 rounded-full border border-border px-3 py-1.5 text-[12px] text-text-subtle">{lang === 'es' ? 'Mensaje' : 'Message'}</span>
              <button type="button" onClick={() => setStep(Math.min(SCREENS.length - 1, step + 1))} disabled={step === SCREENS.length - 1} className="rounded-full bg-brand px-3 py-1.5 text-[12px] font-semibold text-white disabled:opacity-40">
                {lang === 'es' ? 'Siguiente' : 'Next'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
