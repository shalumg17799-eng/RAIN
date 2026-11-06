/**
 * Every browser-storage key the app reads or writes, in one place.
 *
 * The values are the strings already in users' browsers, so changing one signs
 * people out or forgets their state — add new keys here, never rename old ones.
 * Rule: no `localStorage` / `sessionStorage` call outside this list's owners
 * passes review with a bare string.
 */
export const STORAGE_KEYS = {
  /** sessionStorage — the tab's sign-in scope: `'ultra'` (platform) or a client id. */
  session: 'ultra_session',
  /** localStorage — the client the picker last opened. */
  selectedClient: 'selected_client',
  /** sessionStorage — the active persona id for this tab. */
  activePersona: 'active_persona',
  /** sessionStorage — the brand filter of multi-brand tenants (Newfold). */
  activeBrand: 'newfold_active_brand',
  /** sessionStorage — governance audit trail of confidence decisions. */
  confidenceAudit: 'nfcu.audit.v1',
  /** sessionStorage — thumbs up/down feedback on AI messages. */
  messageFeedback: 'nfcu.feedback.v1',
  /** sessionStorage — the escalation threshold set on the governance bar. */
  escalationThreshold: 'nfcu.threshold',
} as const;

export type StorageKey = (typeof STORAGE_KEYS)[keyof typeof STORAGE_KEYS];
