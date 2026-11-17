import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Globe, SendHorizontal } from 'lucide-react';
import type { Lang, PatientStepId } from '@/data/rain/_shared/patient';
import { PATIENT, UI, matchScripted, readingPoints, readingReply } from '@/data/rain/_shared/patient';
import type { PatientDataAnswer, PatientQuery } from '@/data/rain/_shared/patientQueries';
import { askPatientData, namesPatientQuery, patientQueries } from '@/data/rain/_shared/patientQueries';
import type { LindaState, LindaTurn } from '@/components/value-based-care/shell/store';
import { lindaAsk, lindaAskData, lindaShareReading, setLindaLang, setLindaWeekly } from '@/components/value-based-care/shell/store';
import { ReadingForm, ReadingResult, ReadingTrend, RefillCard, VisitOptions, VisitSummary, WeekCards } from './patientCards';

/**
 * Ask AI for patients (spec v2.1 "Patient experience"): Linda's conversation
 * in her phone's browser. Clinic brand first, the product and Radiant in small
 * type, a language switch in the header that rewrites the whole page at once
 * (history, chips and cards are stored by step, not as text), large type, no
 * navigation, no workbenches, no capability tags.
 *
 * Her data questions are answered live by the backend: her own records (appointments, reminders, readings,
 * care gaps, contact preferences) and public data for her town and county (drive time, broadband, blood
 * pressure, shortage area, language). Scripted steps and clinical questions are matched first, as before.
 */

function aiText(turn: LindaTurn, lang: Lang): string {
  if (turn.data) return turn.data.text;
  const s = PATIENT.steps[turn.step!];
  if (turn.step === 'pt_bp_result' && turn.reading) return readingReply(turn.reading, lang);
  if (turn.mobile && s.aiMobile) return s.aiMobile[lang];
  return (turn.after && s.aiAfter ? s.aiAfter : s.ai)[lang];
}

/** A backend answer: the rows of one of her queries, as a small table that scrolls sideways on the phone. */
function DataAnswer({ answer, lang }: { answer: PatientDataAnswer; lang: Lang }) {
  if (!answer.columns.length) return null;
  const fmt = (v: unknown) => (v === null || v === undefined || v === '' ? '–' : typeof v === 'number' ? v.toLocaleString('en-US') : String(v));
  return (
    <div className="rounded-2xl border border-border bg-surface p-3">
      {answer.caption && <p className="text-[12px] font-bold uppercase tracking-wide text-text-muted">{answer.caption}</p>}
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full text-left text-[13px]">
          <thead>
            <tr>
              {answer.columns.map((c) => (
                <th key={c.key} scope="col" className="whitespace-nowrap border-b border-border px-2 py-1 font-semibold text-text-muted">{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {answer.rows.slice(0, 8).map((r, i) => (
              <tr key={i}>
                {answer.columns.map((c) => (
                  <td key={c.key} className="whitespace-nowrap border-b border-border-subtle px-2 py-1 text-text">{fmt(r[c.key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-text-subtle">{UI.dataNote[lang]}</p>
    </div>
  );
}

/** Her readings as they were at that turn, so later readings never rewrite an earlier card. */
const asOf = (turn: LindaTurn, lang: Lang) => readingPoints({ homeReading: turn.reading ?? null, afterVisit: !!turn.after }, lang);

export default function PatientChat({ linda }: { linda: LindaState }) {
  const { lang, thread } = linda;
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [queries, setQueries] = useState<PatientQuery[]>([]);
  const scroller = useRef<HTMLDivElement>(null);
  const newest = useRef<HTMLLIElement>(null);
  const lastAi = [...thread].reverse().find((x) => x.who === 'ai');
  const lastAiId = lastAi?.id;

  // Bring the start of the newest exchange (her question, or the day divider) into view, so a long answer reads from the top.
  const anchorId = [...thread].reverse().find((x) => x.who !== 'ai')?.id;
  // Scrolls only the conversation, never the page around the phone.
  useEffect(() => {
    const box = scroller.current;
    const el = newest.current;
    if (thread.length <= 1 || !box || !el) return;
    const top = el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop - 8;
    box.scrollTo({ top, behavior: 'smooth' });
  }, [thread.length]);

  // Her data questions (her records and her county), from the backend.
  useEffect(() => {
    let live = true;
    void patientQueries().then((qs) => live && setQueries(qs));
    return () => {
      live = false;
    };
  }, []);

  const ask = (step: PatientStepId) => lindaAsk(step);
  /** Ask the backend; true when it answered with her data (or refused someone else's). */
  const askData = async (q: string) => {
    setBusy(true);
    try {
      const answer = await askPatientData(q);
      if (answer) lindaAskData(q, answer);
      return !!answer;
    } finally {
      setBusy(false);
    }
  };
  // A scripted step or a clinical question first (as before); then one of her data questions by id or wording;
  // then a scripted phrase; then the backend for anything else; then the fallback.
  const route = async (q: string) => {
    const m = matchScripted(q);
    if (m.how === 'exact' || m.how === 'clinical') return lindaAsk(m.step, q);
    if (namesPatientQuery(q, queries) && (await askData(q))) return undefined;
    if (m.how === 'phrase') return lindaAsk(m.step, q);
    if (await askData(q)) return undefined;
    return lindaAsk('pt_fallback', q);
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = text.trim();
    if (!q || busy) return;
    setText('');
    void route(q);
  };

  const card = (turn: LindaTurn) => {
    if (turn.data) return <DataAnswer answer={turn.data} lang={lang} />;
    const s = PATIENT.steps[turn.step!];
    const latest = turn.id === lastAiId;
    switch (s.card) {
      case 'week':
        return <WeekCards lang={lang} onPick={ask} />;
      case 'bpForm':
        return <ReadingForm lang={lang} active={latest} shared={latest ? null : linda.homeReading} onShare={lindaShareReading} />;
      case 'bpResult':
        return turn.reading ? <ReadingResult reading={turn.reading} points={asOf(turn, lang)} lang={lang} /> : null;
      case 'options':
        return <VisitOptions lang={lang} chosen={linda.visit} active={latest && !linda.visit} onConfirm={ask} />;
      case 'summary':
        return <VisitSummary lang={lang} weekly={linda.weekly} onWeekly={setLindaWeekly} />;
      case 'refill':
        return <RefillCard lang={lang} mailed={linda.refillMailed} />;
      case 'readings':
        return (
          <div className="rounded-2xl border border-border bg-surface p-3">
            <p className="text-[13px] font-bold uppercase tracking-wide text-text-muted">{UI.readingsTitle[lang]}</p>
            <ReadingTrend points={asOf(turn, lang)} lang={lang} />
          </div>
        );
      default:
        return null;
    }
  };

  const chips = lastAi && !lastAi.data ? PATIENT.steps[lastAi.step!].chips : [];
  const dataChips = lastAi?.data ? lastAi.data.chips : [];

  return (
    <div className="flex h-full min-h-0 flex-col bg-bg" lang={lang}>
      <header className="flex items-center justify-between gap-2 border-b border-border bg-surface px-4 py-2.5">
        <div className="min-w-0">
          <p className="truncate text-[18px] font-bold leading-tight text-brand">{UI.brand[lang]}</p>
          <p className="truncate text-[11px] text-text-muted">Ask AI · {UI.poweredBy[lang]}</p>
        </div>
        <button
          type="button"
          onClick={() => setLindaLang(lang === 'en' ? 'es' : 'en')}
          aria-label={UI.switchLabel[lang]}
          className="inline-flex min-h-11 flex-shrink-0 items-center gap-1.5 rounded-full border-2 border-brand px-3 text-[15px] font-bold text-brand hover:bg-brand/5"
        >
          <Globe className="h-5 w-5" aria-hidden="true" /> {UI.switchTo[lang]}
        </button>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-3 py-3" aria-live="polite">
        <ol className="space-y-3">
          {thread.map((turn) => {
            if (turn.who === 'divider')
              return (
                <li key={turn.id} ref={turn.id === anchorId ? newest : undefined} className="flex justify-center">
                  <span className="rounded-full bg-surface-2 px-3 py-1 text-[13px] font-semibold text-text-muted">{UI.afterDivider[lang]}</span>
                </li>
              );
            if (turn.who === 'me')
              return (
                <li key={turn.id} ref={turn.id === anchorId ? newest : undefined} className="flex justify-end">
                  <p className="max-w-[85%] rounded-2xl rounded-br-md bg-brand px-3.5 py-2.5 text-[16px] leading-snug text-white">
                    <span className="sr-only">{UI.you[lang]}: </span>
                    {turn.raw === undefined ? PATIENT.steps[turn.step!].label[lang] : typeof turn.raw === 'string' ? turn.raw : turn.raw[lang]}
                  </p>
                </li>
              );
            return (
              <li key={turn.id} className="space-y-2">
                <p className="max-w-[92%] rounded-2xl rounded-bl-md bg-surface px-3.5 py-2.5 text-[16px] leading-snug text-text shadow-sm">{aiText(turn, lang)}</p>
                {card(turn)}
              </li>
            );
          })}
        </ol>
        {chips.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {chips.map((c) => (
              <button key={c} type="button" onClick={() => ask(c)} className="min-h-11 rounded-full border-2 border-brand bg-surface px-3.5 text-[15px] font-semibold text-brand hover:bg-brand/5">
                {PATIENT.steps[c].label[lang]}
              </button>
            ))}
          </div>
        )}
        {dataChips.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {dataChips.map((c) => (
              <button key={c} type="button" disabled={busy} onClick={() => void askData(c)} className="min-h-11 rounded-full border-2 border-brand bg-surface px-3.5 text-left text-[15px] font-semibold text-brand hover:bg-brand/5">
                {c}
              </button>
            ))}
          </div>
        )}
        {busy && <p className="mt-3 text-[14px] text-text-muted">{UI.checking[lang]}</p>}
      </div>

      <div className="border-t border-border bg-surface px-3 pb-2 pt-2">
        <p className="mb-1 text-[12px] font-semibold text-text-muted">{UI.suggested[lang]}</p>
        <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-2">
          {PATIENT.queries.map((q) => (
            <button key={q.to + q.en} type="button" onClick={() => lindaAsk(q.to, { en: q.en, es: q.es })} className="min-h-10 flex-shrink-0 rounded-full bg-surface-2 px-3 text-[14px] font-semibold text-text hover:bg-brand/10">
              {q[lang]}
            </button>
          ))}
        </div>
        {queries.length > 0 && (
          <>
            <p className="mb-1 text-[12px] font-semibold text-text-muted">{UI.records[lang]}</p>
            <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-2">
              {queries.map((q) => (
                <button key={q.id} type="button" disabled={busy} onClick={() => void askData(q.question)} className="min-h-10 flex-shrink-0 rounded-full bg-surface-2 px-3 text-[14px] font-semibold text-text hover:bg-brand/10">
                  {q.question}
                </button>
              ))}
            </div>
          </>
        )}
        <form onSubmit={submit} className="flex items-center gap-2">
          <label htmlFor="linda-ask" className="sr-only">
            {UI.askPlaceholder[lang]}
          </label>
          <input
            id="linda-ask"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={UI.askPlaceholder[lang]}
            className="h-12 min-w-0 flex-1 rounded-full border-2 border-border bg-surface px-4 text-[16px] text-text placeholder:text-text-subtle focus:border-brand focus:outline-none"
          />
          <button type="submit" aria-label={UI.send[lang]} disabled={!text.trim() || busy} className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-brand text-white disabled:opacity-40">
            <SendHorizontal className="h-5 w-5" aria-hidden="true" />
          </button>
        </form>
      </div>
    </div>
  );
}
