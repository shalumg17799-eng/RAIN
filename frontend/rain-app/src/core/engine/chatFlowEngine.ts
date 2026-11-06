/**
 * chatFlowEngine — the PURE resolution logic behind the scripted chat.
 *
 * Extracted from the old `useChatFlow` hook so it can be unit-tested without
 * React. Given a user's chip/text and a persona's ChatFlowConfig, it decides
 * which flowKey to respond with, walking the same fallback ladder the demo
 * relied on:
 *   1. explicit chip → flowKey map (incl. the `__next_signal__` token)
 *   2. exact user_query match
 *      (2b. the persona's own `matchUtterance` parser, when it supplies one)
 *   3. substring match against user_query
 *   4. keyword-scored match across query/message text
 *   5. per-persona `__default__` flow (if defined)
 *
 * Rungs 3 and 4 fail OPEN: they will find something for almost any input. A
 * persona that would rather admit it did not understand sets `strictMatch` on
 * its ChatFlowConfig, which raises both bars — see the notes at each rung.
 */

import type { ChatFlowConfig } from '../types';

const STOPWORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'to', 'for', 'of', 'on', 'in', 'at', 'me', 'my', 'our', 'i',
  'what', 'show', 'tell', 'give', 'about', 'this', 'that', 'these', 'those', 'it', 'can',
  'do', 'does', 'please', 'some', 'any', 'how', 'why', 'where', 'which', 'who', 'and', 'or', 'but',
]);

export const NEXT_SIGNAL_TOKEN = '__next_signal__';
export const DEFAULT_FLOW_KEY = '__default__';

/** Shortest input the strict substring rung will consider. */
const STRICT_MIN_LENGTH = 8;

export interface ResolveResult {
  /** The flowKey to respond with, or null when nothing matched and no default. */
  flowKey: string | null;
  /** True when the match consumed a signal-sequence step. */
  isSignal: boolean;
}

/** Resolve the next signal in the persona's signal sequence. */
export function resolveNextSignal(config: ChatFlowConfig, signalIndex: number): string | null {
  return config.signalSequence[signalIndex] ?? null;
}

/**
 * Resolve a user chip/text to a flowKey using the full fallback ladder.
 * Pure: callers manage signal-index state and message side-effects.
 */
export function resolveFlowKey(config: ChatFlowConfig, input: string): ResolveResult {
  const { chatFlows, chipToFlowKey } = config;

  // 1. explicit chip map
  const mapped = chipToFlowKey[input];
  if (mapped === NEXT_SIGNAL_TOKEN) return { flowKey: NEXT_SIGNAL_TOKEN, isSignal: true };
  if (mapped && chatFlows[mapped]) {
    return { flowKey: mapped, isSignal: config.signalSequence.includes(mapped) };
  }

  // 2. exact user_query
  const exact = Object.keys(chatFlows).find((k) => chatFlows[k].user_query === input);
  if (exact) return { flowKey: exact, isSignal: config.signalSequence.includes(exact) };

  // 2b. persona-supplied parser (opt-in; see ChatFlowConfig.matchUtterance)
  const parsed = config.matchUtterance?.(input);
  if (parsed && chatFlows[parsed]) return { flowKey: parsed, isSignal: config.signalSequence.includes(parsed) };

  // 3. substring match (requires a non-empty user_query on both sides)
  //
  // Under `strictMatch` only the "the user typed a whole known question"
  // direction survives, and only above a length floor. The other direction —
  // a stored user_query CONTAINING the input — is what makes three characters
  // of gibberish land on a real node, and the floor is what stops "report"
  // from being treated as a request.
  const lower = input.toLowerCase();
  const strict = config.strictMatch === true;
  const partial = Object.keys(chatFlows).find((k) => {
    const q = (chatFlows[k].user_query || '').toLowerCase().trim();
    if (!q) return false;
    if (strict) return lower.length >= STRICT_MIN_LENGTH && lower.includes(q);
    return q.includes(lower) || lower.includes(q);
  });
  if (partial) return { flowKey: partial, isSignal: config.signalSequence.includes(partial) };

  // 4. keyword-scored match
  const words = lower.split(/\W+/).filter((w) => w.length > 2 && !STOPWORDS.has(w));
  if (words.length > 0) {
    let bestKey: string | null = null;
    let bestScore = 0;
    for (const key of Object.keys(chatFlows)) {
      if (key.startsWith('__')) continue;
      const f = chatFlows[key];
      const corpus = `${f.user_query || ''} ${f.ai_message || ''} ${f.ai_response || ''}`.toLowerCase();
      let score = 0;
      for (const w of words) if (corpus.includes(w)) score += 1;
      if (score > bestScore) {
        bestScore = score;
        bestKey = key;
      }
    }
    // A single shared word is not evidence of intent. Under `strictMatch` a
    // short query has to clear the same bar as a long one, so "asdfgh permit"
    // falls through to __default__ instead of landing on the permit draft.
    const minScore = strict ? 2 : words.length <= 2 ? 1 : 2;
    if (bestKey && bestScore >= minScore) {
      return { flowKey: bestKey, isSignal: config.signalSequence.includes(bestKey) };
    }
  }

  // 5. per-persona default
  if (chatFlows[DEFAULT_FLOW_KEY]) return { flowKey: DEFAULT_FLOW_KEY, isSignal: false };

  return { flowKey: null, isSignal: false };
}
