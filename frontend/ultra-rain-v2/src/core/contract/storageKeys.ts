/**
 * Every browser-storage key the app reads or writes, in one place.
 *
 * The values are the strings already in users' browsers, so changing one signs
 * people out or forgets their state — add new keys here, never rename old ones.
 * Rule: no `localStorage` / `sessionStorage` call outside this list's owners
 * passes review with a bare string.
 *
 * This build's own names: the session and the governance keys carry a
 * `rain` prefix, and the app runs on its own port, so a browser that has
 * also run the multi-tenant platform keeps the two apart.
 */
export const STORAGE_KEYS = {
  /** sessionStorage — the tab's sign-in scope: the client id (`rain`). */
  session: 'rain_session',
  /** localStorage — the client this browser last signed in to. */
  selectedClient: 'selected_client',
  /** sessionStorage — the active persona id for this tab. */
  activePersona: 'active_persona',
  /** sessionStorage — governance audit trail of confidence decisions. */
  confidenceAudit: 'rain.audit.v1',
  /** sessionStorage — thumbs up/down feedback on AI messages. */
  messageFeedback: 'rain.feedback.v1',
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];
