import { useSyncExternalStore } from 'react';
import { EVENTS } from '@core/contract/events';
import { CARE } from '@/data/rain/_shared/constants';
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

export interface RainState {
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
  /** Linda's post-visit reading has come in (closes her BP gap). */
  lindaReading: boolean;
  briefEdits: Record<string, string>;
  sentNotes: Record<string, boolean>;
}

const initial = (): RainState => ({
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
  briefEdits: {},
  sentNotes: {},
});

let state = initial();
let seq = 0;
const listeners = new Set<() => void>();
const set = (patch: Partial<RainState>) => {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
};
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};

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

/** Back to the morning (Reset demo, a new sign-in). Keeps the auto-open setting. */
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
}

/** Undo a hand-logged outcome (a misclick, or the patient calls back). */
export function clearContact(memberId: string) {
  if (!state.contacts[memberId]) return;
  const { [memberId]: _cleared, ...rest } = state.contacts;
  set({ contacts: rest });
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
}

/** Linda's home reading closes her gap: one more member controlled. */
export function recordLindaReading() {
  if (state.lindaReading) return;
  set({ lindaReading: true, campaign: { ...state.campaign, controlled: state.campaign.controlled + 1 } });
}

export function sign(who: 'cio' | 'cmo') {
  if (state.signed[who]) return;
  set({ signed: { ...state.signed, [who]: true } });
}

export const isReleased = (s: RainState = state) => s.signed.cio && s.signed.cmo;

export const editBrief = (key: string, text: string) => set({ briefEdits: { ...state.briefEdits, [key]: text } });
export const sendNote = (id: string) => set({ sentNotes: { ...state.sentNotes, [id]: true } });

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
