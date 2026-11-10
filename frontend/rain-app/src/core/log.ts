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

/**
 * Data-provenance proof. Unlike the dev channels above, this prints in every
 * build, production included, on purpose: it is how anyone can confirm in
 * devtools that every value on screen came from the backend (the boot load in
 * data/rain/_shared/backendData.ts and each API call in core/api/proof.ts).
 * Silent under tests.
 */
const proofOn = import.meta.env.MODE !== 'test';

export const PROOF_STYLE = {
  badge: 'background:#0b3d91;color:#fff;padding:2px 6px;border-radius:3px;font-weight:600',
  alert: 'background:#cf222e;color:#fff;padding:2px 6px;border-radius:3px;font-weight:600',
  ok: 'color:#1a7f37;font-weight:600',
  bad: 'color:#cf222e;font-weight:600',
  bold: 'font-weight:600',
} as const;

export const proof = {
  group: (...args: unknown[]) => { if (proofOn) console.group(...args); },
  log: (...args: unknown[]) => { if (proofOn) console.log(...args); },
  table: (rows: unknown) => { if (proofOn) console.table(rows); },
  end: () => { if (proofOn) console.groupEnd(); },
  error: (...args: unknown[]) => { if (proofOn) console.error(...args); },
};
