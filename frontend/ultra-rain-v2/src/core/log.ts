/**
 * The app's only console. Development diagnostics go through here so that a
 * production demo never prints to a client's devtools, and so the standard
 * audit can hold every other file to zero console calls.
 *
 * One thing prints in every build except tests: the backend API calls, one
 * collapsed entry per call (written by core/api/proof.ts through `apiConsole`),
 * so anyone can see in devtools that every value comes from the RAIN backend.
 */
const isTest = import.meta.env.MODE === 'test';
const enabled = import.meta.env.DEV && !isTest;

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

/**
 * The backend API call log: a collapsed group whose title is the call (method, path,
 * status, time) and whose body is the call's details. Prints in every build except tests.
 */
export const apiConsole = {
  call(title: string, styles: string[], details: Record<string, unknown>): void {
    if (isTest) return;
    console.groupCollapsed(title, ...styles);
    console.log(details);
    console.groupEnd();
  },
};
