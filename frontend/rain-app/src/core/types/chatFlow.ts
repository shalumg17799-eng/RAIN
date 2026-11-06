/**
 * The scripted-conversation contract. Each persona ships a set of flows keyed
 * by `flowKey`; the chat engine walks them deterministically in response to
 * chip clicks / typed queries. This is the heart of the demo runtime.
 */

import type { CapabilityId } from './capability';

/** A UI element the AI attaches to a message (action cards, tables, etc.). */
export interface UiComponentSpec {
  type: string;
  [key: string]: unknown;
}

/** One scripted turn. */
export interface ChatFlow {
  /** The user utterance that leads here (used by the free-text fallback matcher). */
  user_query?: string;
  /** Primary AI response text (either field is used across demos). */
  ai_message?: string;
  ai_response?: string;
  /** Data sources cited under the message. */
  data_sources_used?: string[];
  /** Suggested follow-up chips offered after this turn. */
  suggested_chips?: string[];
  /** Structured UI to render with this message. */
  ui_components_to_render?: UiComponentSpec[];
  confidence?: number;
  capability?: CapabilityId | string;
  /** For action turns: keyed responses after the user confirms an action. */
  post_confirm_response?: Record<string, string>;
  [key: string]: unknown;
}

/** Post-confirm wiring for a single action button. */
export interface ActionConfirmConfig {
  responseKey: string;
  nextChips?: string[];
}

/**
 * The full scripted config for one persona — everything `useChatFlow` needs.
 * Each persona's lives in its own module, `src/data/flows/<personaId>.js`.
 */
export interface ChatFlowConfig {
  chatFlows: Record<string, ChatFlow>;
  /** Chip label → flowKey (or the special `__next_signal__` token). */
  chipToFlowKey: Record<string, string>;
  /** Ordered flowKeys that advance the "turn" counter (drives context panel). */
  askTurnSequence: string[];
  /** Ordered flowKeys walked by the "Next signal" progression. */
  signalSequence: string[];
  /** flowKey of the action turn whose confirmations are wired below. */
  actionTurnKey?: string;
  actionConfirmMap?: Record<string, ActionConfirmConfig>;

  // ─── Optional, opt-in hooks. Absent on every persona that does not need
  // them, so the engine behaves exactly as before for those. Added for the
  // Maryland DoIT tenant, whose briefing has to know which of the day's
  // action items the user already finished. ────────────────────────────

  /**
   * Rewrite a flowKey the instant before it is rendered.
   *
   * The chip map and the `greetingFlowKey` are both static, so a persona whose
   * briefing changes as the session progresses cannot express that with data
   * alone. This is the one seam where a manifest can say "when they come back
   * to the briefing, give them the variant that matches what is still open".
   *
   * Must be pure enough to call during a render-adjacent timeout: read a module
   * store, return a flowKey. An unknown key falls back to the original.
   */
  resolveFlowKey?: (flowKey: string) => string;

  /**
   * Deliver the opening (greeting) message at once instead of after the
   * typing pause. While the greeting types, the workspace shows neither the
   * greeting header nor any card, so a persona whose briefing IS that first
   * message looked blank for a moment after every persona switch (SCLAC, Oct
   * 30 review). Answers to chips still type. Absent, the greeting types as
   * before.
   */
  instantGreeting?: boolean;

  /**
   * Fired once the message for `flowKey` has been committed to the thread.
   *
   * Progress tracking belongs here rather than in a card's click handler: every
   * modal's confirm label is ALSO offered as a chip on the same turn, so a user
   * who clicks the chip instead of the dialog would otherwise advance the
   * conversation without ever recording that the work was done.
   */
  onFlowEnter?: (flowKey: string) => void;

  /**
   * Fired when the persona's conversation starts fresh: the workspace mounts
   * (opening Ask from the nav, signing in, switching to this persona). NOT
   * fired by "Back to briefing", which re-greets inside the same session, nor
   * when a persisted thread is restored.
   *
   * Added for the Comptroller of Maryland tenant, whose demo keeps progress in
   * a module store (record updated, package generated, approvals) and must
   * start again from the first beat every time Ask is opened. Absent on every
   * other persona, so their behaviour is unchanged.
   */
  onSessionStart?: () => void;

  /**
   * Hold a turn back until the user confirms it. Called with the flowKey a chip
   * or typed message resolved to, before anything is added to the thread.
   * Return true to take over: nothing happens until the persona calls
   * `proceed()` (which then runs the turn exactly as if just clicked), and if
   * it never does — the user cancelled — the thread and chips stay as they
   * were. Return false to let the turn run now.
   *
   * Added for the Comptroller of Maryland tenant, whose "Update the record"
   * chip changes a sourced figure and must show a confirmation first. Absent
   * on every other persona, so their behaviour is unchanged.
   */
  interceptFlow?: (flowKey: string, proceed: () => void) => boolean;

  /**
   * Tighten the free-text matching ladder (rungs 3 and 4 of `resolveFlowKey`).
   *
   * The default rungs fail open by design — a short or unfamiliar utterance
   * lands on whatever node happens to share a word with it, which reads as the
   * assistant repeating itself rather than admitting it did not understand.
   * Personas that would rather fall through to `__default__` set this.
   */
  strictMatch?: boolean;

  /**
   * Map free text to a flowKey before the fuzzy rungs run (between rung 2,
   * exact `user_query`, and rung 3, substring). Return null to fall through.
   * A returned key that is not in `chatFlows` is ignored.
   *
   * Added for SCLAC, whose audience is invited to ask a question of their own
   * ("what's next-step clarity at Long Beach?"): the persona parses the KPI,
   * courthouse and intent and answers from flows it generated from the seed.
   * Absent on every other persona, so their matching is unchanged.
   */
  matchUtterance?: (input: string) => string | null;
}
