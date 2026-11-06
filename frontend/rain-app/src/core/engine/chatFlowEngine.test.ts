import { describe, it, expect } from 'vitest';
import { resolveFlowKey, resolveNextSignal, NEXT_SIGNAL_TOKEN } from './chatFlowEngine';
import type { ChatFlowConfig } from '../types';

const config: ChatFlowConfig = {
  chatFlows: {
    turn_1: { user_query: "What's driving the mortgage drop-off?", ai_message: 'Mortgage funnel analysis…' },
    turn_2: { user_query: 'Who are these members?', ai_message: 'Segment breakdown…' },
    sig_1: { ai_message: 'Signal one' },
    sig_2: { ai_message: 'Signal two' },
    __default__: { ai_message: 'Here is what I can help with' },
  },
  chipToFlowKey: {
    'Who are these members?': 'turn_2',
    'Next signal': NEXT_SIGNAL_TOKEN,
  },
  askTurnSequence: ['turn_1', 'turn_2'],
  signalSequence: ['sig_1', 'sig_2'],
};

describe('resolveFlowKey', () => {
  it('resolves an explicit chip map', () => {
    expect(resolveFlowKey(config, 'Who are these members?')).toEqual({ flowKey: 'turn_2', isSignal: false });
  });

  it('passes through the next-signal token', () => {
    expect(resolveFlowKey(config, 'Next signal')).toEqual({ flowKey: NEXT_SIGNAL_TOKEN, isSignal: true });
  });

  it('matches an exact user_query not in the chip map', () => {
    expect(resolveFlowKey(config, "What's driving the mortgage drop-off?").flowKey).toBe('turn_1');
  });

  it('substring-matches a partial query', () => {
    expect(resolveFlowKey(config, 'mortgage drop-off').flowKey).toBe('turn_1');
  });

  it('keyword-scores free-form text', () => {
    expect(resolveFlowKey(config, 'tell me about member segments').flowKey).toBe('turn_2');
  });

  it('flags a signal-sequence match', () => {
    expect(resolveFlowKey(config, 'Signal one')).toEqual({ flowKey: 'sig_1', isSignal: true });
  });

  it('falls back to __default__ for unmatched input', () => {
    expect(resolveFlowKey(config, 'zxcvbnm qwerty').flowKey).toBe('__default__');
  });

  it('returns null when nothing matches and no default exists', () => {
    const noDefault: ChatFlowConfig = { ...config, chatFlows: { turn_1: config.chatFlows.turn_1 } };
    expect(resolveFlowKey(noDefault, 'zxcvbnm qwerty').flowKey).toBeNull();
  });
});

describe('resolveNextSignal', () => {
  it('returns the signal at the index, then null past the end', () => {
    expect(resolveNextSignal(config, 0)).toBe('sig_1');
    expect(resolveNextSignal(config, 1)).toBe('sig_2');
    expect(resolveNextSignal(config, 2)).toBeNull();
  });
});

/**
 * `strictMatch` — opt-in, and OFF everywhere it is not declared.
 *
 * The default ladder deliberately fails open, which is right for a scripted demo
 * whose chips are the intended path. It is wrong for a persona that would rather
 * say it did not understand: rung 3 matches a stored user_query that merely
 * CONTAINS the input, and rung 4 accepts a single shared word, so three
 * characters of noise land on a real answer. These tests pin both behaviours so
 * the tenants relying on the loose one cannot be changed by accident.
 */
describe('strictMatch', () => {
  const strict: ChatFlowConfig = { ...config, strictMatch: true };

  it('falls through to __default__ on input the loose ladder would place', () => {
    // "members" is contained by turn_2's user_query, so rung 3 claims it.
    expect(resolveFlowKey(config, 'members').flowKey).toBe('turn_2');
    expect(resolveFlowKey(strict, 'members').flowKey).toBe('__default__');
  });

  it('still resolves a full question the user typed out', () => {
    expect(resolveFlowKey(strict, 'Who are these members?').flowKey).toBe('turn_2');
    expect(resolveFlowKey(strict, 'so who are these members?').flowKey).toBe('turn_2');
  });

  it('sends gibberish to __default__ rather than the nearest keyword', () => {
    expect(resolveFlowKey(strict, 'zxqw plork frobnitz').flowKey).toBe('__default__');
  });

  it('needs two matching keywords, not one', () => {
    // One shared word ("mortgage") is enough for the loose ladder, not the strict one.
    expect(resolveFlowKey(config, 'mortgage').flowKey).toBe('turn_1');
    expect(resolveFlowKey(strict, 'mortgage').flowKey).toBe('__default__');
    expect(resolveFlowKey(strict, 'mortgage drop-off').flowKey).toBe('turn_1');
  });

  it('leaves the chip map and exact-match rungs untouched', () => {
    expect(resolveFlowKey(strict, 'Next signal')).toEqual({ flowKey: NEXT_SIGNAL_TOKEN, isSignal: true });
    expect(resolveFlowKey(strict, "What's driving the mortgage drop-off?").flowKey).toBe('turn_1');
  });
});

describe('matchUtterance (opt-in parser, rung 2b)', () => {
  const parsed = {
    ...config,
    strictMatch: true,
    matchUtterance: (t: string) => (/clarity at long beach/i.test(t) ? 'turn_2' : /bogus/i.test(t) ? 'no_such_flow' : null),
  };

  it('routes free text the persona recognises', () => {
    expect(resolveFlowKey(parsed, "what's next-step clarity at Long Beach").flowKey).toBe('turn_2');
  });

  it('falls through when it returns null or an unknown key', () => {
    expect(resolveFlowKey(parsed, 'zxqw plork frobnitz').flowKey).toBe('__default__');
    expect(resolveFlowKey(parsed, 'bogus words here').flowKey).toBe('__default__');
  });

  it('never overrides the chip map', () => {
    expect(resolveFlowKey(parsed, 'Next signal')).toEqual({ flowKey: NEXT_SIGNAL_TOKEN, isSignal: true });
  });

  it('is absent by default, so nothing changes for other personas', () => {
    expect(config).not.toHaveProperty('matchUtterance');
  });
});
