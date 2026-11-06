/**
 * The one place the app reads the clock or draws a random number.
 *
 * Typing delays, live KPI drift, timestamps on feedback and audit entries,
 * elapsed timers: every one goes through here, so a test (or, later, a backend
 * that owns time) controls all of them by controlling these three functions.
 * The render nets fake `Date` and seed `Math.random`, which these call.
 */

/** Milliseconds since the epoch, now. */
export const now = (): number => Date.now();

/** Now, as an ISO-8601 string (for timestamps that are stored or shown). */
export const nowIso = (): string => new Date(now()).toISOString();

/** A number in [0, 1). */
export const random = (): number => Math.random();
