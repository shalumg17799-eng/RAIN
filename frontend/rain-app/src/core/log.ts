/**
 * The app's only console. Development diagnostics go through here so that a
 * production demo never prints to a client's devtools, and so the standard
 * audit can hold every other file to zero console calls.
 */
const enabled = import.meta.env.DEV && import.meta.env.MODE !== 'test';

/** Progress of a developer tool (the guided demo runner). */
export function devInfo(...args: unknown[]): void {
  if (enabled) console.info(...args);
}

/** A misconfiguration a developer should see (bad manifest, unrouted chip). */
export function devWarn(...args: unknown[]): void {
  if (enabled) console.warn(...args);
}

/** Something broke that the UI already recovered from (error boundary, failed load). */
export function devError(...args: unknown[]): void {
  if (enabled) console.error(...args);
}
