/**
 * Linda's state in the RAIN demo store (spec v2.1, Use Case C): her phone's
 * screen, her conversation, and what each of her steps changed for the care
 * team. The actions live in `store.ts` beside the rest of the closed loop.
 */
import type { Lang, PatientStepId, Reading } from '@/data/rain/_shared/patient';
import type { PatientDataAnswer } from '@/data/rain/_shared/patientQueries';

/** One line of Linda's conversation: stored by step, so a language switch rewrites the whole history. */
export interface LindaTurn {
  id: number;
  who: 'me' | 'ai' | 'divider';
  step?: PatientStepId;
  /** An answer the backend ran live from one of her data questions (her records, or public data for her county). */
  data?: PatientDataAnswer;
  /** What she typed (shown as typed), or a suggested question (shown in her language). */
  raw?: string | Record<Lang, string>;
  reading?: Reading;
  /** The turn came after her visit (answers that change once it has happened). */
  after?: boolean;
  /** The turn came after her mobile clinic switch was approved. */
  mobile?: boolean;
}

export type LindaVisitChoice = 'keep' | 'mobile' | 'ride';

export interface LindaState {
  lang: Lang;
  /** Her phone: the text with the link, the one-time code screen, then the conversation. */
  phase: 'sms' | 'code' | 'chat';
  thread: LindaTurn[];
  /** She opened the secure link (marks the 72-hour reminder as read). */
  opened: boolean;
  homeReading: Reading | null;
  /** A reading at the urgent line (alerts the Worklist). */
  alert: Reading | null;
  visit: LindaVisitChoice | null;
  /** Brandon approved her mobile clinic switch or ride request. */
  requestApproved: boolean;
  afterVisit: boolean;
  refillMailed: boolean;
  weekly: boolean;
  /** She asked her care team to call her back. */
  message: boolean;
}

export const lindaInitial = (lang: Lang = 'en'): LindaState => ({
  lang,
  phase: 'sms',
  thread: [],
  opened: false,
  homeReading: null,
  alert: null,
  visit: null,
  requestApproved: false,
  afterVisit: false,
  refillMailed: false,
  weekly: true,
  message: false,
});
