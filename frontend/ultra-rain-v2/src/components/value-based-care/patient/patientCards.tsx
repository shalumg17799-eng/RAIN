import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { AlertTriangle, Car, CheckCircle2, ChevronRight, MapPin, Package, Stethoscope, Video } from 'lucide-react';
import { resolveIcon } from '@core/contract/icons';
import { LINDA, bpText } from '@/data/rain/_shared/constants';
import type { Lang, PatientStepId, Reading, ReadingPoint as Point } from '@/data/rain/_shared/patient';
import { PATIENT, UI, isPlausible, isUrgent, meetsGoal } from '@/data/rain/_shared/patient';
import type { LindaVisitChoice } from '@/components/value-based-care/shell/store';

/**
 * The cards in Linda's phone conversation (spec v2.1 "Guided patient flow"):
 * large type, large tap targets, plain words, both languages. They show her
 * own information only, never a score, a ranking or another patient.
 */

const t = (key: keyof typeof UI, lang: Lang) => UI[key][lang];

function Card({ children, tone = 'neutral', className = '' }: { children: ReactNode; tone?: 'neutral' | 'good' | 'critical'; className?: string }) {
  const tones = { neutral: 'border-border bg-surface', good: 'border-success/40 bg-success-subtle', critical: 'border-critical/50 bg-critical-subtle' };
  return <div className={`rounded-2xl border p-3 ${tones[tone]} ${className}`}>{children}</div>;
}

/** Step 1: her three to-dos for the week, each one tap from its step. */
export function WeekCards({ lang, onPick }: { lang: Lang; onPick: (step: PatientStepId) => void }) {
  return (
    <div className="space-y-2">
      <p className="text-[13px] font-bold uppercase tracking-wide text-text-muted">{t('thisWeek', lang)}</p>
      {PATIENT.signals.map((c) => {
        const Icon = resolveIcon(c.icon);
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => onPick(c.chip)}
            className="flex min-h-14 w-full items-center gap-3 rounded-2xl border border-border bg-surface p-3 text-left shadow-sm hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
          >
            <span className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-brand/10 text-brand">{Icon ? <Icon className="h-6 w-6" aria-hidden="true" /> : null}</span>
            <span className="min-w-0 flex-1">
              <span className="block text-[16px] font-bold leading-tight text-text">{c.title[lang]}</span>
              <span className="block text-[14px] font-semibold text-brand">{c.when[lang]}</span>
              <span className="block text-[14px] leading-snug text-text-muted">{c.text[lang]}</span>
            </span>
            <ChevronRight className="h-5 w-5 flex-shrink-0 text-text-subtle" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}

/** Step 2: two large number fields, or "Sync my cuff" (which reads her cuff: 142/88). */
export function ReadingForm({ lang, active, shared, onShare }: { lang: Lang; active: boolean; shared: Reading | null; onShare: (r: Reading) => void }) {
  const [sys, setSys] = useState('');
  const [dia, setDia] = useState('');
  const [error, setError] = useState(false);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const r = { sys: Number(sys), dia: Number(dia) };
    if (!isPlausible(r)) return setError(true);
    setError(false);
    onShare(r);
  };
  if (!active)
    return (
      <Card>
        <p className="text-[15px] text-text-muted">{shared ? `${t('shared', lang)}: ${bpText(shared)}` : t('share', lang)}</p>
      </Card>
    );
  const field = (id: string, label: string, value: string, set: (v: string) => void) => (
    <label htmlFor={id} className="block">
      <span className="mb-1 block text-[14px] font-semibold text-text">{label}</span>
      <input
        id={id}
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={3}
        value={value}
        onChange={(e) => set(e.target.value.replace(/\D/g, ''))}
        className="h-14 w-full rounded-xl border-2 border-border bg-surface px-3 text-center text-[26px] font-bold tabular-nums text-text focus:border-brand focus:outline-none"
      />
    </label>
  );
  return (
    <Card>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          {field('linda-sys', t('top', lang), sys, setSys)}
          {field('linda-dia', t('bottom', lang), dia, setDia)}
        </div>
        {error && (
          <p role="alert" className="text-[14px] font-semibold text-critical-700">
            {t('checkNumbers', lang)}
          </p>
        )}
        <div className="grid gap-2">
          <button type="submit" disabled={!sys || !dia} className="min-h-12 rounded-xl bg-brand px-4 text-[16px] font-bold text-white disabled:opacity-40">
            {t('share', lang)}
          </button>
          <button
            type="button"
            onClick={() => {
              setSys(String(LINDA.home.sys));
              setDia(String(LINDA.home.dia));
              setError(false);
            }}
            className="min-h-12 rounded-xl border-2 border-brand px-4 text-[16px] font-bold text-brand hover:bg-brand/5"
          >
            {t('sync', lang)}
          </button>
        </div>
      </form>
    </Card>
  );
}

/** A small trend of her last three readings (top number) against the goal line. */
export function ReadingTrend({ points, lang }: { points: Point[]; lang: Lang }) {
  const W = 300;
  const H = 128;
  const pad = { l: 12, r: 12, t: 22, b: 26 };
  const values = [...points.map((p) => p.r.sys), LINDA.goal.sys];
  const lo = Math.min(...values) - 6;
  const hi = Math.max(...values) + 6;
  const x = (i: number) => pad.l + (points.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (points.length - 1));
  const y = (v: number) => pad.t + ((hi - v) / (hi - lo)) * (H - pad.t - pad.b);
  const goalY = y(LINDA.goal.sys);
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${t('readingsTitle', lang)}: ${points.map((p) => `${p.label} ${bpText(p.r)}`).join(', ')}. ${t('goal', lang)}.`}>
        <line x1={pad.l} x2={W - pad.r} y1={goalY} y2={goalY} className="stroke-success" strokeWidth={2} strokeDasharray="6 4" />
        <text x={pad.l} y={goalY + 14} textAnchor="start" className="fill-success-700 text-[11px] font-semibold">
          {t('goal', lang)}
        </text>
        <polyline points={points.map((p, i) => `${x(i)},${y(p.r.sys)}`).join(' ')} fill="none" className="stroke-brand" strokeWidth={2.5} />
        {points.map((p, i) => (
          <g key={p.label}>
            <circle cx={x(i)} cy={y(p.r.sys)} r={5} className={meetsGoal(p.r) ? 'fill-success' : 'fill-brand'} />
            <text x={x(i)} y={y(p.r.sys) - 9} textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'} className="fill-text text-[12px] font-bold">
              {bpText(p.r)}
            </text>
            <text x={x(i)} y={H - 6} textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'} className="fill-text-muted text-[11px]">
              {p.label}
            </text>
          </g>
        ))}
      </svg>
    </figure>
  );
}

/** Step 2 result: the trend, and the clinic's fixed safety message at the urgent line. */
export function ReadingResult({ reading, points, lang }: { reading: Reading; points: Point[]; lang: Lang }) {
  const urgent = isUrgent(reading);
  return (
    <div className="space-y-2">
      {urgent && (
        <Card tone="critical">
          <p role="alert" className="flex items-start gap-2 text-[15px] font-bold leading-snug text-critical-800">
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden="true" />
            {t('urgent', lang)}
          </p>
        </Card>
      )}
      <Card tone={meetsGoal(reading) ? 'good' : 'neutral'}>
        <p className="text-[13px] font-bold uppercase tracking-wide text-text-muted">{t('readingsTitle', lang)}</p>
        <ReadingTrend points={points} lang={lang} />
      </Card>
    </div>
  );
}

const OPTIONS: Array<{ id: LindaVisitChoice; step: PatientStepId; icon: typeof Video; title: keyof typeof UI; when: keyof typeof UI; drive: number }> = [
  { id: 'keep', step: 'pt_keep', icon: Video, title: 'optVideo', when: 'optVideoWhen', drive: 0 },
  { id: 'mobile', step: 'pt_mobile', icon: MapPin, title: 'optMobile', when: 'optMobileWhen', drive: LINDA.mobileClinic.driveMin },
  { id: 'ride', step: 'pt_ride', icon: Car, title: 'optRide', when: 'optRideWhen', drive: LINDA.driveMin },
];

/** Step 3: three ways to see her care team, each with its drive time, and a Confirm button. */
export function VisitOptions({ lang, chosen, active, onConfirm }: { lang: Lang; chosen: LindaVisitChoice | null; active: boolean; onConfirm: (step: PatientStepId) => void }) {
  const [pick, setPick] = useState<LindaVisitChoice>(chosen ?? 'keep');
  return (
    <Card>
      <fieldset disabled={!active} className="space-y-2">
        <legend className="sr-only">{t('confirm', lang)}</legend>
        {OPTIONS.map((o) => {
          const Icon = o.icon;
          const on = (active ? pick : chosen) === o.id;
          return (
            <label key={o.id} className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border-2 p-2.5 ${on ? 'border-brand bg-brand/5' : 'border-border'}`}>
              <input type="radio" name="linda-visit" value={o.id} checked={on} onChange={() => setPick(o.id)} className="h-5 w-5 accent-brand" />
              <Icon className="h-6 w-6 flex-shrink-0 text-brand" aria-hidden="true" />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className="text-[16px] font-bold leading-tight text-text">{t(o.title, lang)}</span>
                  <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[12.5px] font-bold tabular-nums text-text">{o.drive ? `${o.drive} ${t('drive', lang)}` : t('noDrive', lang)}</span>
                </span>
                <span className="block text-[13.5px] leading-snug text-text-muted">{t(o.when, lang)}</span>
              </span>
            </label>
          );
        })}
        {active && (
          <button type="button" onClick={() => onConfirm(OPTIONS.find((o) => o.id === pick)!.step)} className="min-h-12 w-full rounded-xl bg-brand px-4 text-[16px] font-bold text-white">
            {t('confirm', lang)}
          </button>
        )}
      </fieldset>
    </Card>
  );
}

function RefillTrack({ lang, mailed }: { lang: Lang; mailed: boolean }) {
  const steps = [
    { key: 'ordered', done: true },
    { key: 'mailed', done: mailed },
    { key: 'arrives', done: false },
  ] as const;
  return (
    <ol className="mt-1 grid grid-cols-3 gap-1">
      {steps.map((s) => (
        <li key={s.key} className={`rounded-lg px-1.5 py-1.5 text-center text-[13px] font-semibold ${s.done ? 'bg-success-subtle text-success-700' : 'bg-surface-2 text-text-muted'}`}>
          {s.done && <CheckCircle2 className="mx-auto mb-0.5 h-4 w-4" aria-hidden="true" />}
          {t(s.key, lang)}
        </li>
      ))}
    </ol>
  );
}

/** Refill by mail: her metformin, tracked to her door. */
export function RefillCard({ lang, mailed }: { lang: Lang; mailed: boolean }) {
  return (
    <Card>
      <p className="flex items-center gap-2 text-[15px] font-bold text-text">
        <Package className="h-5 w-5 text-brand" aria-hidden="true" /> {t('refillTitle', lang)}
      </p>
      <RefillTrack lang={lang} mailed={mailed} />
    </Card>
  );
}

/** Step 4: the after-visit summary "From your care team", refill tracking and the weekly reminder. */
export function VisitSummary({ lang, weekly, onWeekly }: { lang: Lang; weekly: boolean; onWeekly: (on: boolean) => void }) {
  return (
    <Card tone="good" className="space-y-3">
      <p className="flex items-center gap-2 text-[13px] font-bold uppercase tracking-wide text-success-700">
        <Stethoscope className="h-4 w-4" aria-hidden="true" /> {t('fromTeam', lang)}
      </p>
      <div className="flex items-end justify-between gap-2 rounded-xl bg-surface p-2.5">
        <span>
          <span className="block text-[13px] font-semibold text-text-muted">{t('bpToday', lang)}</span>
          <span className="block text-[28px] font-bold leading-none tabular-nums text-text">{bpText(LINDA.visitReading)}</span>
        </span>
        <span className="inline-flex items-center gap-1 rounded-lg bg-success-subtle px-2 py-1 text-[13px] font-bold text-success-700">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> {t('meetsGoal', lang)}
        </span>
      </div>
      <div className="rounded-xl bg-surface p-2.5">
        <p className="text-[13px] font-semibold text-text-muted">{t('medicine', lang)}</p>
        <p className="text-[15px] font-semibold text-text">{t('sameWay', lang)}</p>
      </div>
      <div className="rounded-xl bg-surface p-2.5">
        <p className="text-[13px] font-semibold text-text-muted">{t('refillTitle', lang)}</p>
        <RefillTrack lang={lang} mailed />
      </div>
      <label className="flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-xl bg-surface p-2.5">
        <span className="text-[15px] font-semibold text-text">{t('weekly', lang)}</span>
        <input type="checkbox" role="switch" checked={weekly} onChange={(e) => onWeekly(e.target.checked)} className="h-6 w-6 flex-shrink-0 accent-brand" />
      </label>
    </Card>
  );
}
