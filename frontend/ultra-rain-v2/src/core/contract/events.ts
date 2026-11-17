/**
 * Every window event the app uses as a message bus, in one place.
 *
 * These are the decoupling seam between a card deep in a chat thread and the
 * workspace or overlay that reacts to it (open the deck, ask a question, switch
 * persona). Before this registry the names were bare strings repeated in up to
 * six files each; a typo silently did nothing.
 *
 * This build names its events after its one client (`rain:*`).
 */
export const EVENTS = {
  // ── Workbench questions and resets ──
  rainAsk: 'rain:ask',
  rainResetThreads: 'rain:reset-threads',

  // ── Governance telemetry (confidence escalations, message feedback) ──
  escalation: 'rain:escalation',
  feedback: 'rain:feedback',
} as const;

export type EventName = (typeof EVENTS)[keyof typeof EVENTS];

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
