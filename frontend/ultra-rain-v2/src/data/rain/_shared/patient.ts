/**
 * Linda Garcia's contract (spec v2.1, Use Case C), typed. The same seven
 * top-level keys as the operator personas, served by the backend
 * (GET /api/v4/ui2/data → section "contracts", key "patient": a template whose
 * visit day, date and time and her last reading are filled from her own computed
 * record in rain_v4.synthetic):
 * her this-week cards are her `signals`, her guided and side turns are her
 * `steps`, her suggested questions are her `queries`, and her `handoffs` are
 * the Use Case C connections into Teresa's, Brandon's and Dr. Castellanos's
 * workbenches. Every string ships in English and Spanish (English by default).
 *
 * This module also holds the rules the phone view applies to what she types:
 * the reading reply (the spec's sentence for 142/88, the same sentence shape
 * for any other reading), the clinic's fixed safety message, and the matcher
 * that routes a typed question to a step or to her care team.
 */
import { LINDA, ORG } from './constants';
import type { WorkbenchId } from './contract';
import { rainValue } from './backendData';

export type Lang = 'en' | 'es';
export type Bi = Record<Lang, string>;

export interface PatientCard {
  id: string;
  /** An icon registry id (core/contract/icons.ts). */
  icon: string;
  title: Bi;
  when: Bi;
  text: Bi;
  /** The step a tap on the card opens. */
  chip: PatientStepId;
}

export type PatientCardKind = 'week' | 'bpForm' | 'bpResult' | 'options' | 'summary' | 'refill' | 'readings';

export interface PatientStep {
  /** The spec step this scripts (1 to 4); side turns have none. */
  step?: number;
  /** The chip or question that reaches this step. */
  label: Bi;
  /** Typed words (either language) that reach this step. */
  asks: string[];
  ai: Bi;
  /** The answer once her visit has happened, where it differs. */
  aiAfter?: Bi;
  /** The answer once her switch to the mobile clinic is approved, where it differs. */
  aiMobile?: Bi;
  card?: PatientCardKind;
  sources: string[];
  chips: PatientStepId[];
  /** The Use Case C connections this step makes (hand-off ids). */
  connects?: string[];
}

export interface PatientQuery extends Bi {
  to: PatientStepId;
}

export interface PatientHandoff {
  id: string;
  title: string;
  count: number;
  to: string;
  workbench: WorkbenchId;
  detail: string;
}

export interface PatientContract {
  signals: PatientCard[];
  kpis: never[];
  steps: Record<string, PatientStep>;
  queries: PatientQuery[];
  viz: Record<string, { type: string; props: Record<string, unknown> }>;
  handoffs: PatientHandoff[];
  workbenches: never[];
}

export type PatientStepId =
  | 'pt_week'
  | 'pt_bp'
  | 'pt_bp_result'
  | 'pt_drive'
  | 'pt_keep'
  | 'pt_mobile'
  | 'pt_ride'
  | 'pt_after'
  | 'pt_visit'
  | 'pt_join'
  | 'pt_next'
  | 'pt_refill'
  | 'pt_readings'
  | 'pt_care'
  | 'pt_clinical'
  | 'pt_fallback';

export const PATIENT = rainValue<PatientContract>('contracts', 'patient');

/** "jueves" as "Jueves". */
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const patientStep = (id: PatientStepId) => PATIENT.steps[id];

/** Screen words that are not turns: the entry text, the code screen, the header, the cards. */
export const UI: Record<string, Bi> = {
  brand: { en: `${ORG.networkShort} Care`, es: `${ORG.networkShort} Care` },
  poweredBy: { en: 'Powered by Radiant Digital', es: 'Con tecnología de Radiant Digital' },
  switchTo: { en: 'Español', es: 'English' },
  switchLabel: { en: 'Cambiar a español', es: 'Switch to English' },
  messages: { en: 'Messages', es: 'Mensajes' },
  textMessage: { en: 'Text message', es: 'Mensaje de texto' },
  sms: {
    en: `${ORG.networkShort}: Hi ${LINDA.first}, your care team has this week's to-dos ready for you. Open your secure link: https://${LINDA.site}/l/4821`,
    es: `${ORG.networkShort}: Hola ${LINDA.first}, su equipo de salud tiene sus pendientes de esta semana. Abra su enlace seguro: https://${LINDA.site}/l/4821`,
  },
  smsHint: { en: 'Tap the link to open it.', es: 'Toque el enlace para abrirlo.' },
  signingIn: { en: 'Signing you in', es: 'Entrando' },
  codeNote: { en: 'One-time code from your text. No password needed.', es: 'Código de un solo uso de su texto. No necesita contraseña.' },
  thisWeek: { en: 'This week', es: 'Esta semana' },
  you: { en: 'You', es: 'Usted' },
  askPlaceholder: { en: 'Type a question', es: 'Escriba una pregunta' },
  send: { en: 'Send', es: 'Enviar' },
  suggested: { en: 'Questions you can ask', es: 'Preguntas que puede hacer' },
  top: { en: 'Top number', es: 'Número de arriba' },
  bottom: { en: 'Bottom number', es: 'Número de abajo' },
  sync: { en: 'Sync my cuff', es: 'Sincronizar mi monitor' },
  share: { en: 'Share my reading', es: 'Compartir mi lectura' },
  shared: { en: 'Reading shared', es: 'Lectura compartida' },
  checkNumbers: { en: 'Please check the numbers. The top number is usually between 70 and 250.', es: 'Revise los números. El número de arriba casi siempre está entre 70 y 250.' },
  goal: { en: 'Goal: under 140 over 90', es: 'Meta: menos de 140 sobre 90' },
  readingsTitle: { en: 'Your readings', es: 'Sus lecturas' },
  today: { en: 'Today', es: 'Hoy' },
  visitDay: { en: 'Visit', es: 'Cita' },
  drive: { en: 'min drive', es: 'min de manejo' },
  noDrive: { en: 'No drive', es: 'Sin manejar' },
  confirm: { en: 'Confirm', es: 'Confirmar' },
  optVideo: { en: 'Video visit', es: 'Cita por video' },
  optVideoWhen: { en: `${LINDA.visit.day}, ${LINDA.visit.time}, from this phone`, es: `${cap(LINDA.visit.esDay)}, ${LINDA.visit.time}, desde este teléfono` },
  optMobile: { en: 'Mobile clinic', es: 'Clínica móvil' },
  optMobileWhen: { en: 'Battle Mountain, Tuesday, Nov 10, 10:00 AM', es: 'Battle Mountain, martes 10 de nov., 10:00 AM' },
  optRide: { en: 'Clinic with free ride', es: 'Clínica con viaje gratis' },
  optRideWhen: { en: `${LINDA.clinic}. Your health plan covers the ride.`, es: `${LINDA.clinic}. Su plan de salud cubre el viaje.` },
  fromTeam: { en: 'From your care team', es: 'De su equipo de salud' },
  bpToday: { en: 'Blood pressure today', es: 'Presión hoy' },
  meetsGoal: { en: 'Meets your goal', es: 'Cumple su meta' },
  medicine: { en: 'Medicine', es: 'Medicina' },
  sameWay: { en: 'Keep taking it the same way.', es: 'Siga tomándola igual.' },
  refillTitle: { en: 'Metformin refill', es: 'Metformina' },
  ordered: { en: 'Ordered', es: 'Pedida' },
  mailed: { en: 'Mailed', es: 'Enviada' },
  arrives: { en: 'Arrives Saturday', es: 'Llega el sábado' },
  weekly: { en: 'Weekly reminder to take my blood pressure', es: 'Recordatorio semanal para tomarme la presión' },
  afterDivider: { en: `${LINDA.visit.day}, ${LINDA.visit.date}, after your visit`, es: `${cap(LINDA.visit.esDay)} ${LINDA.visit.esDate}, después de su cita` },
  chosen: { en: 'Your choice', es: 'Su elección' },
  records: { en: 'Ask about your records and your county', es: 'Pregunte por sus datos y su condado' },
  checking: { en: 'Checking your records…', es: 'Revisando sus datos…' },
  dataNote: { en: 'From your records and public data, answered live.', es: 'De sus datos y datos públicos, al momento (en inglés).' },
  urgent: {
    en: 'This reading is high. We let your care team know. If you have chest pain, trouble breathing or a bad headache, call 911.',
    es: 'Esta lectura está alta. Le avisamos a su equipo de salud. Si tiene dolor de pecho, dificultad para respirar o un dolor de cabeza fuerte, llame al 911.',
  },
};

export interface Reading {
  sys: number;
  dia: number;
}

export interface ReadingPoint {
  label: string;
  r: Reading;
}

/** Her readings for the trend, oldest first: June (illustrative), August, then what she has shared since; the last three. */
export function readingPoints(l: { homeReading: Reading | null; afterVisit: boolean }, lang: Lang): ReadingPoint[] {
  const en = lang === 'en';
  const pts: ReadingPoint[] = [
    { label: en ? 'Jun' : 'jun', r: LINDA.earlier },
    { label: en ? 'Aug' : 'ago', r: LINDA.last },
  ];
  if (l.homeReading) pts.push({ label: UI.today[lang], r: l.homeReading });
  if (l.afterVisit) pts.push({ label: UI.visitDay[lang], r: LINDA.visitReading });
  return pts.slice(-3);
}

const over = (r: Reading, lang: Lang) => `${r.sys} ${lang === 'en' ? 'over' : 'sobre'} ${r.dia}`;

export const meetsGoal = (r: Reading) => r.sys < LINDA.goal.sys && r.dia < LINDA.goal.dia;
export const isUrgent = (r: Reading) => r.sys >= LINDA.urgent.sys || r.dia >= LINDA.urgent.dia;
/** A plausible cuff reading; anything else asks her to check the numbers. */
export const isPlausible = (r: Reading) => r.sys >= 70 && r.sys <= 250 && r.dia >= 40 && r.dia <= 150 && r.sys > r.dia;

/**
 * Her reply to a home reading. For 142/88 this is the spec's sentence word for
 * word; any other reading gets the same shape: the reading, the comparison
 * with August when it is better, and where it stands against her goal. A
 * reading at the urgent line gets only the reading; the clinic's fixed safety
 * message follows on its own card (spec "Safety message").
 */
export function readingReply(r: Reading, lang: Lang): string {
  const en = lang === 'en';
  const parts = [en ? `Thank you, Linda. Your reading is ${over(r, lang)}.` : `Gracias, Linda. Su presión es ${over(r, lang)}.`];
  if (isUrgent(r)) return parts[0];
  const last = LINDA.last;
  if (r.sys < last.sys && r.dia <= last.dia)
    parts.push(en ? `That is better than your last one in ${last.month.en} (${over(last, lang)}).` : `Está mejor que la última vez en ${last.month.es} (${over(last, lang)}).`);
  if (meetsGoal(r)) parts.push(en ? 'That meets your goal of under 140 over 90.' : 'Eso cumple su meta de menos de 140 sobre 90.');
  else if (r.sys < LINDA.goal.sys + 10 && r.dia < LINDA.goal.dia + 10) parts.push(en ? 'Your goal is under 140 over 90, so you are close.' : 'Su meta es menos de 140 sobre 90, así que está cerca.');
  else parts.push(en ? 'Your goal is under 140 over 90.' : 'Su meta es menos de 140 sobre 90.');
  parts.push(en ? 'Your care team will see this before your video visit on Thursday.' : 'Su equipo de salud la verá antes de su cita del jueves.');
  return parts.join(' ');
}

const CLINICAL = /\b(pill|pills|dose|dosage|side effect|dizzy|pain|hurt|should i take|stop taking|pastilla|pastillas|dosis|efecto|mareo|mareada|dolor|duele|debo tomar|dejar de tomar)\b/i;

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[¿?¡!.,]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

/**
 * Where a typed question goes, and how it matched: an exact chip or suggested
 * question first (`exact`), then a clinical question (`clinical`: always to the
 * care team, never answered), then the longest matching phrase (`phrase`), else
 * nothing (`none`, the fallback step). The phone asks the backend's data
 * questions between these (components/value-based-care/patient/PatientChat.tsx).
 */
export function matchScripted(text: string): { step: PatientStepId; how: 'exact' | 'clinical' | 'phrase' | 'none' } {
  const t = norm(text);
  if (!t) return { step: 'pt_fallback', how: 'none' };
  for (const [id, s] of Object.entries(PATIENT.steps)) if (norm(s.label.en) === t || norm(s.label.es) === t) return { step: id as PatientStepId, how: 'exact' };
  for (const q of PATIENT.queries) if (norm(q.en) === t || norm(q.es) === t) return { step: q.to, how: 'exact' };
  if (CLINICAL.test(text) || CLINICAL.test(t)) return { step: 'pt_clinical', how: 'clinical' };
  let best: { id: PatientStepId; len: number } | null = null;
  for (const [id, s] of Object.entries(PATIENT.steps))
    for (const a of s.asks) {
      const n = norm(a);
      if (n && t.includes(n) && (!best || n.length > best.len)) best = { id: id as PatientStepId, len: n.length };
    }
  return best ? { step: best.id, how: 'phrase' } : { step: 'pt_fallback', how: 'none' };
}

/** The scripted step a typed question reaches (the fallback when none). */
export function matchQuestion(text: string): PatientStepId {
  return matchScripted(text).step;
}
