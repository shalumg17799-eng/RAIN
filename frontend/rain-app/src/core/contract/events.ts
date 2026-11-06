/**
 * Every window event the app uses as a message bus, in one place.
 *
 * These are the decoupling seam between a card deep in a chat thread and the
 * workspace or overlay that reacts to it (open the deck, ask a question, switch
 * persona). Before this registry the names were bare strings repeated in up to
 * six files each; a typo silently did nothing.
 *
 * The string values are unchanged from what each tenant shipped, so moving a
 * call site onto this registry is a pure refactor.
 */
export const EVENTS = {
  // ── Overlays a persona's manifest opens via `features.overlayOpenEvent` ──
  ussfcuCeoOpenPresentation: 'ussfcu-ceo:open-presentation',
  esfcuCeoOpenPresentation: 'esfcu-ceo:open-presentation',
  esfcuCroOpenPresentation: 'esfcu-cro:open-presentation',
  sclacOpenBriefing: 'sclac:open-briefing',
  amisaHrOpenAssignment: 'amisa-hr:open-assignment',
  doitResidentOpenSurvey: 'doit-resident:open-survey',
  mdcRevopsPublishConfirm: 'mdc:revops-publish-confirm',

  // ── Questions asked from outside the conversation (`features.askEvent`) ──
  sclacAsk: 'sclac-ask',
  mdcAsk: 'mdc:ask',

  // ── Persona hand-off (Comptroller of Maryland) ──
  mdcSwitchPersona: 'mdc:switch-persona',
  mdcResetThreads: 'mdc:reset-threads',

  // ── Persona hand-off and card questions (Lyte Corporate Intelligence) ──
  lyteAsk: 'lyte:ask',
  lyteSwitchPersona: 'lyte:switch-persona',
  lyteResetThreads: 'lyte:reset-threads',

  // ── Workbench questions and resets (RAIN) ──
  rainAsk: 'rain:ask',
  rainResetThreads: 'rain:reset-threads',

  // ── Governance telemetry (NFCU) ──
  nfcuEscalation: 'nfcu:escalation',
  nfcuFeedback: 'nfcu:feedback',
} as const;

export type EventName = (typeof EVENTS)[keyof typeof EVENTS];

/**
 * Presentation-deck namespaces. A deck listens for `<ns>:open-chat`,
 * `<ns>:open-closing` and `<ns>:open-lineage`; `deckEvent()` builds the name so
 * the three suffixes are spelled once.
 */
export const DECK_NAMESPACES = {
  ussfcuCeo: 'ussfcu-ceo-deck',
  esfcuCeo: 'esfcu-ceo-deck',
  esfcuCro: 'esfcu-cro-deck',
  sclacBriefing: 'sclac-briefing',
} as const;

export type DeckAction = 'open-chat' | 'open-closing' | 'open-lineage';

export function deckEvent(namespace: string, action: DeckAction): string {
  return `${namespace}:${action}`;
}

/** Dispatch a registered event on `window`. Safe to call during SSR/tests. */
export function emitEvent(name: string, detail?: unknown): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(name, detail === undefined ? undefined : { detail }));
}

/** Listen for a registered event; returns the unsubscribe function. */
export function onEvent<T = unknown>(name: string, handler: (detail: T, event: CustomEvent<T>) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const listener = (e: Event) => handler((e as CustomEvent<T>).detail, e as CustomEvent<T>);
  window.addEventListener(name, listener);
  return () => window.removeEventListener(name, listener);
}
