/**
 * The app's only console.
 *
 * The browser console shows one thing: the backend API calls, one collapsed entry
 * per call (written by core/api/proof.ts through `apiConsole`). Nothing else prints.
 *
 * Developer diagnostics (`devInfo`, `devWarn`, `devError`: the guided demo runner,
 * a bad manifest, an unrouted chip, a recovered render error) stay silent unless a
 * developer turns them on in the browser: localStorage.setItem('rain:debug', '1').
 * Everything is silent under tests.
 */
const isTest = import.meta.env.MODE === 'test';

function debugOn(): boolean {
  if (isTest) return false;
  try {
    return globalThis.localStorage?.getItem('rain:debug') === '1';
  } catch {
    return false;
  }
}

/** Progress of a developer tool (the guided demo runner). */
export function devInfo(...args: unknown[]): void {
  if (debugOn()) console.info(...args);
}

/** A misconfiguration a developer should see (bad manifest, unrouted chip). */
export function devWarn(...args: unknown[]): void {
  if (debugOn()) console.warn(...args);
}

/** Something broke that the UI already recovered from (error boundary, failed load). */
export function devError(...args: unknown[]): void {
  if (debugOn()) console.error(...args);
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
