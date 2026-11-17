import { useSyncExternalStore } from 'react';
import { EVENTS } from '@core/contract/events';
import { CARE, LINDA } from '@/data/rain/_shared/constants';
import { onFlow, postFlow } from '@/data/rain/_shared/flowApi';
import type { Lang, PatientStepId, Reading } from '@/data/rain/_shared/patient';
import { isUrgent, meetsGoal } from '@/data/rain/_shared/patient';
import type { PatientDataAnswer } from '@/data/rain/_shared/patientQueries';
import type { LindaState, LindaTurn, LindaVisitChoice } from './linda';
import { lindaInitial } from './linda';

export type { LindaState, LindaTurn, LindaVisitChoice } from './linda';
import type { RainLaunch, WorkbenchId } from '@/data/rain/_shared/contract';
import { parseAction } from '@/data/rain/_shared/contract';
import type { ContactStatus } from '@/data/rain/_shared/records';
import { getCampaignMembers, getTeresaWorklist } from '@/data/rain/_shared/records';

/**
 * The RAIN demo store: what has been approved and handed off, what the
 * Cockpit pane is looking at, the launch a conversation step asked for, and
 * the care team's progress that flows back to the quality gate.
 *
 * Module-scoped because cards render through `manifest.answers`, workbenches
 * render outside the conversation, and an approval in one persona's thread
 * has to show in another persona's workbench (the hand-off is the only data
 * link between Use Case A and B). `resetRainState` returns it to the morning.
 *
 * Every care-team action, and what Linda does on her phone, is also written to the
 * backend (flowApi → POST /api/v4/flow/*): the change is kept in rain_v4.synthetic, the
 * UI data is re-read and recomputed, so another persona, browser or a reload sees it.
 * `resetDemoData` undoes the backend changes too.
 */

export const ASK_EVENT = EVENTS.rainAsk;
export const RESET_THREADS_EVENT = EVENTS.rainResetThreads;

export interface PaneContext {
  /** "Viewing: …" in the pane header. */
  label: string;
  /** Context chips, each a question the conversation answers. */
  chips: string[];
  /** What is selected, for the context answers. */
  kind?: 'member' | 'site' | 'gap' | 'segment' | 'measure' | 'lvMeasure' | 'feature' | 'source' | 'county' | 'slot' | 'booking';
  id?: string;
}

export interface LaunchRequest extends RainLaunch {
  seq: number;
  stepId: string;
}

export interface ValueBasedCareState {
  approved: Record<string, boolean>;
  launch: LaunchRequest | null;
  /** Demo setting: open a launching step's workbench after one second. */
  autoOpen: boolean;
  pane: PaneContext | null;
  paneOpen: boolean | null;
  /** Workbench → its current filter (a pane answer can apply one). */
  filters: Partial<Record<WorkbenchId, string>>;
  /** Rows a pane answer asked the workbench to highlight. */
  highlight: string[];
  campaign: { booked: number; controlled: number };
  contacts: Record<string, ContactStatus>;
  /** Member id → booked slot id. */
  bookings: Record<string, string>;
  /** The member Scheduling opens on. */
  scheduleFor: string | null;
  /** Raj: the access-adjusted model shown as a preview (step 3). */
  fixPreview: boolean;
  signed: { cio: boolean; cmo: boolean };
  cosignRequested: boolean;
  freshnessBanner: boolean;
  targetCounties: string[];
  /** A reading that meets Linda's goal has come in (closes her BP gap). */
  lindaReading: boolean;
  /** Linda's own experience (Use Case C) and what it changes for the care team. */
  linda: LindaState;
  /** The operator persona Linda's view returns to. */
  lastOperator: string | null;
  briefEdits: Record<string, string>;
  sentNotes: Record<string, boolean>;
  /** Bumped after each backend write-back once the recomputed UI data is in. */
  dataVersion: number;
}

const initial = (): ValueBasedCareState => ({
  approved: {},
  launch: null,
  autoOpen: false,
  pane: null,
  paneOpen: null,
  filters: {},
  highlight: [],
  campaign: { booked: CARE.booked, controlled: CARE.controlled },
  contacts: {},
  bookings: {},
  scheduleFor: null,
  fixPreview: false,
  signed: { cio: false, cmo: false },
  cosignRequested: false,
  freshnessBanner: false,
  targetCounties: [],
  lindaReading: false,
  linda: lindaInitial(),
  lastOperator: null,
  briefEdits: {},
  sentNotes: {},
  dataVersion: 0,
});

let state = initial();
let seq = 0;
const listeners = new Set<() => void>();
const set = (patch: Partial<ValueBasedCareState>) => {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
};
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};

// A write-back re-read the backend data: re-render whatever shows it.
onFlow(() => set({ dataVersion: state.dataVersion + 1 }));

export const getRainState = () => state;
export const useRainState = () => useSyncExternalStore(subscribe, getRainState, getRainState);

/**
 * The workbench selection a context answer was about, kept per message: taken
 * when the answer first renders, so selecting another row later never
 * rewrites an earlier answer in the thread.
 */
const snapshots = new Map<string, { kind?: string; id?: string }>();
export function selectionFor(messageId: string | number | undefined): { kind?: string; id?: string } {
  const key = String(messageId ?? '');
  if (!key) return { kind: state.pane?.kind, id: state.pane?.id };
  if (!snapshots.has(key)) snapshots.set(key, { kind: state.pane?.kind, id: state.pane?.id });
  return snapshots.get(key)!;
}

/**
 * The patient view renders outside the app shell, so coming back from it
 * remounts the shell exactly as a new sign-in would. It marks its visit so the
 * session guard keeps the demo's state (the booking and Linda's reading).
 */
let patientVisit = false;
export const markPatientVisit = () => {
  patientVisit = true;
};
export function takePatientVisit() {
  const visited = patientVisit;
  patientVisit = false;
  return visited;
}

/** Back to the morning (Reset demo, a new sign-in). Keeps the auto-open setting; Linda is back to English. */
export function resetRainState() {
  snapshots.clear();
  const autoOpen = state.autoOpen;
  state = { ...initial(), autoOpen };
  listeners.forEach((l) => l());
}

export const setAutoOpen = (autoOpen: boolean) => set({ autoOpen });
export const setPaneOpen = (paneOpen: boolean) => set({ paneOpen });
export const setPane = (pane: PaneContext | null) => {
  if (state.pane?.label === pane?.label && state.pane?.id === pane?.id && state.pane?.chips.join('|') === pane?.chips.join('|')) return;
  set({ pane });
};
export const setFilter = (wb: WorkbenchId, filter: string) => {
  if (state.filters[wb] === filter) return;
  set({ filters: { ...state.filters, [wb]: filter } });
};
export const setHighlight = (ids: string[]) => set({ highlight: ids });

export function approve(...ids: string[]) {
  const next = { ...state.approved };
  let changed = false;
  for (const id of ids)
    if (!next[id]) {
      next[id] = true;
      changed = true;
      void postFlow('handoff', { handoffId: id });
    }
  if (changed) set({ approved: next });
}

export function requestLaunch(stepId: string, launch: RainLaunch) {
  seq += 1;
  set({ launch: { ...launch, seq, stepId } });
}

export function logContact(memberId: string, status: ContactStatus) {
  if (state.contacts[memberId] === status) return;
  set({ contacts: { ...state.contacts, [memberId]: status } });
  void postFlow('contact', { memberId, outcome: status });
}

/** Undo a hand-logged outcome (a misclick, or the patient calls back). */
export function clearContact(memberId: string) {
  if (!state.contacts[memberId]) return;
  const { [memberId]: _cleared, ...rest } = state.contacts;
  set({ contacts: rest });
  void postFlow('contact', { memberId, outcome: 'Not contacted' });
}

export const scheduleMember = (memberId: string | null) => set({ scheduleFor: memberId });

/** A confirmed booking moves the campaign's progress bar (closed loop to Use Case A). */
export function book(memberId: string, slotId: string) {
  if (state.bookings[memberId]) return;
  set({
    bookings: { ...state.bookings, [memberId]: slotId },
    contacts: { ...state.contacts, [memberId]: 'Reached and booked' },
    campaign: { ...state.campaign, booked: state.campaign.booked + 1 },
  });
  void postFlow('book', { memberId, slotId });
}

/** A reading that meets Linda's goal closes her gap: one more member controlled. */
export function recordLindaReading() {
  if (state.lindaReading) return;
  set({ lindaReading: true, campaign: { ...state.campaign, controlled: state.campaign.controlled + 1 } });
}

// ─── Linda's experience (Use Case C) ───────────────────────────────────────

/** Her member id, from her own record (the backend's LINDA). */
export const LINDA_ID = LINDA.memberId;
/** Her Thursday 2:00 PM video visit (Scheduling slot S1). */
const LINDA_SLOT = 'S1';
const MOBILE_SLOT = 'S4';
let turnSeq = 0;

const setLinda = (patch: Partial<LindaState>) => set({ linda: { ...state.linda, ...patch } });
const turn = (t: Omit<LindaTurn, 'id'>): LindaTurn => ({ ...t, id: ++turnSeq });

/** Her language choice stays with her for the rest of the demo, including her next visit to her phone. */
export function setLindaLang(lang: Lang) {
  if (state.linda.lang !== lang) setLinda({ lang });
}

export const setLastOperator = (id: string) => {
  if (state.lastOperator !== id) set({ lastOperator: id });
};

/**
 * She taps the link in her text. The visit it reminds her of is on file
 * whether or not Brandon has booked it in this demo yet, so the story works in
 * either order; opening the link marks the 72-hour reminder as read.
 */
export function lindaOpenLink() {
  if (!state.bookings[LINDA_ID]) book(LINDA_ID, LINDA_SLOT);
  setLinda({ phase: 'code', opened: true });
}

/** The one-time code signs her in: the greeting is her first turn. */
export function lindaSignedIn() {
  if (state.linda.phase === 'chat') return;
  setLinda({ phase: 'chat', thread: state.linda.thread.length ? state.linda.thread : [turn({ who: 'ai', step: 'pt_week' })] });
}

/** A chip, a card, a suggested question or a typed question reaches a step. */
export function lindaAsk(step: PatientStepId, raw?: string | Record<Lang, string>) {
  const l = state.linda;
  const patch: Partial<LindaState> = {};
  if (step === 'pt_keep' || step === 'pt_mobile' || step === 'pt_ride') {
    const choice: LindaVisitChoice = step === 'pt_keep' ? 'keep' : step === 'pt_mobile' ? 'mobile' : 'ride';
    if (l.visit !== choice) {
      Object.assign(patch, { visit: choice, requestApproved: false });
      void postFlow('reply', { memberId: LINDA_ID, reply: choice === 'keep' ? 'C' : 'R' });
    }
  }
  if (step === 'pt_refill') patch.refillMailed = true;
  if (step === 'pt_care' || step === 'pt_clinical') patch.message = true;
  const after = l.afterVisit;
  // A readings answer keeps the readings as they were when she asked.
  const reading = step === 'pt_readings' ? (l.homeReading ?? undefined) : undefined;
  const mobile = l.visit === 'mobile' && l.requestApproved && !after;
  setLinda({ ...patch, thread: [...l.thread, turn({ who: 'me', step: raw ? undefined : step, raw }), turn({ who: 'ai', step, after, reading, mobile })] });
}

/** One of her data questions, answered live by the backend (her records, or public data for her county). */
export function lindaAskData(raw: string, data: PatientDataAnswer) {
  const l = state.linda;
  setLinda({ thread: [...l.thread, turn({ who: 'me', raw }), turn({ who: 'ai', data })] });
}

/**
 * She shares a home reading. It shows on her Worklist row; at the urgent line
 * it alerts the care team; only a reading that meets her goal closes her gap
 * (142/88 does not: the visit still matters).
 */
export function lindaShareReading(r: Reading) {
  const l = state.linda;
  setLinda({
    homeReading: r,
    alert: isUrgent(r) ? r : l.alert,
    thread: [...l.thread, turn({ who: 'me', raw: `${r.sys}/${r.dia}` }), turn({ who: 'ai', step: 'pt_bp_result', reading: r, after: l.afterVisit })],
  });
  void postFlow('reading', { memberId: LINDA_ID, systolic: r.sys, diastolic: r.dia, source: 'home cuff' });
  if (meetsGoal(r)) recordLindaReading();
}

/** Thursday, after the video visit: the 136/84 reading closes her gap and the summary arrives. */
export function lindaAfterVisit() {
  const l = state.linda;
  if (l.afterVisit) return;
  setLinda({ afterVisit: true, refillMailed: true, thread: [...l.thread, turn({ who: 'divider' }), turn({ who: 'ai', step: 'pt_after', after: true })] });
  recordLindaReading();
  void postFlow('reading', { memberId: LINDA_ID, systolic: LINDA.visitReading.sys, diastolic: LINDA.visitReading.dia, source: 'video visit' });
}

export const setLindaWeekly = (weekly: boolean) => setLinda({ weekly });

/** Brandon approves her mobile clinic switch (the booking moves) or her ride. */
export function approveLindaRequest() {
  const l = state.linda;
  if (!l.visit || l.visit === 'keep' || l.requestApproved) return;
  if (l.visit === 'mobile') {
    set({ bookings: { ...state.bookings, [LINDA_ID]: MOBILE_SLOT } });
    // the backend moves her booking (her earlier BP recheck is released); Reset demo undoes it
    void postFlow('book', { memberId: LINDA_ID, slotId: MOBILE_SLOT });
  }
  setLinda({ requestApproved: true });
}

/** Start Linda's phone over (her language choice stays); the care team keeps what she already did. */
export function restartLinda() {
  set({ linda: { ...lindaInitial(state.linda.lang) } });
}

export function sign(who: 'cio' | 'cmo') {
  if (state.signed[who]) return;
  set({ signed: { ...state.signed, [who]: true } });
  void postFlow('signoff', { who });
}

export const isReleased = (s: ValueBasedCareState = state) => s.signed.cio && s.signed.cmo;

export const editBrief = (key: string, text: string) => set({ briefEdits: { ...state.briefEdits, [key]: text } });
export const sendNote = (id: string) => {
  set({ sentNotes: { ...state.sentNotes, [id]: true } });
  void postFlow('note', { noteId: id });
};

/** Reset demo: undo every backend write-back too (the data goes back to the generated morning). */
export const resetDemoData = () => postFlow('reset');

/** Run a step's `action` (see the persona JSON). */
export function runAction(action: string | undefined) {
  if (!action) return;
  const { verb, args } = parseAction(action);
  if (verb === 'approve') approve(...args);
  else if (verb === 'preview' && args[0] === 'fix') set({ fixPreview: true });
  else if (verb === 'sign' && (args[0] === 'cio' || args[0] === 'cmo')) sign(args[0]);
  else if (verb === 'request' && args[0] === 'cosign') set({ cosignRequested: true });
  else if (verb === 'banner') set({ freshnessBanner: args[0] === 'on' });
  else if (verb === 'target') set({ targetCounties: args });
  else if (verb === 'highlight') set({ highlight: highlightIds(args[0]) });
}

/** The rows a pane answer asks the workbench to highlight. */
function highlightIds(set: string | undefined): string[] {
  if (set === 'campaignTop10') return getCampaignMembers().slice(0, 10).map((m) => m.id);
  if (set === 'teresaTop5') return getTeresaWorklist().slice(0, 5).map((m) => m.id);
  return [];
}

/** How many RAIN conversations are mounted (the footer counts itself). */
let workspaces = 0;
export function markWorkspaceMounted() {
  workspaces += 1;
  return () => {
    workspaces -= 1;
  };
}

/** Ask a question from a workbench or card: through the conversation when one is on screen. */
export function ask(text: string): boolean {
  if (workspaces > 0 && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(ASK_EVENT, { detail: { text } }));
    return true;
  }
  return false;
}
