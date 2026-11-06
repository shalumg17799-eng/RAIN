/**
 * Flow integrity — every persona's scripted conversation is wired end to end.
 *
 * A chip that routes nowhere does nothing when clicked, and a route that names
 * a missing turn renders nothing; neither throws, so neither shows up anywhere
 * but in front of a client. These checks run over every registered persona:
 *
 *  1. every `chipToFlowKey` target is a defined turn (or a runtime token);
 *  2. every chip a turn offers, and every initial chip, resolves the way the
 *     engine resolves a click: chip map, then a turn's exact `user_query`,
 *     then the persona's own `matchUtterance`;
 *  3. every turn in `askTurnSequence` / `signalSequence` / `actionTurnKey` exists;
 *  4. every `signalToChip` chip resolves;
 *  5. every wired action confirm has a response on the action turn, and the
 *     chips it offers afterwards resolve;
 *  6. there is a `__default__` turn, so a typed question nothing matches gets
 *     an answer (and `POST /ask` a turn) instead of silence.
 */
import { describe, it, expect } from 'vitest';
import { getMarkets } from './registry';
import { resolveFlowKey } from '../engine/chatFlowEngine';
import type { PersonaManifest } from '../types';

const RUNTIME_TOKENS = new Set(['__next_signal__', '__default__']);
/** Chips the conversation hook answers itself, before the chip map. */
const HOOK_CHIPS = new Set(['Next signal', 'Yes, walk me through them']);

const entries = getMarkets().flatMap((market) =>
  market.clients.flatMap((client) => client.personas.map((persona) => ({ client, persona }))),
);

function resolver(manifest: PersonaManifest) {
  const { chatFlows, chipToFlowKey, matchUtterance } = manifest.flows;
  const byQuery = new Map<string, string>();
  for (const [key, flow] of Object.entries(chatFlows)) {
    const q = (flow as { user_query?: string }).user_query;
    if (q && !byQuery.has(q)) byQuery.set(q, key);
  }
  // The engine's deterministic rungs only (1, 2, 2b). A chip that needs the
  // fuzzy rungs to land works by luck and lands wherever the words point.
  return (chip: string): string | null => {
    if (HOOK_CHIPS.has(chip)) return '__next_signal__';
    if (chip in chipToFlowKey) return chipToFlowKey[chip];
    const q = byQuery.get(chip);
    if (q) return q;
    const matched = matchUtterance?.(chip);
    if (matched && matched in chatFlows) return matched;
    return null;
  };
}

describe('scripted flows are wired end to end', () => {
  it.each(entries.map((e) => [`${e.client.id}/${e.persona.id}`, e] as const))(
    '%s',
    async (_label, { persona }) => {
      const manifest = (await persona.load()).default as PersonaManifest;
      const { chatFlows, chipToFlowKey, askTurnSequence, signalSequence, actionTurnKey } = manifest.flows;
      const resolve = resolver(manifest);
      const problems: string[] = [];
      const known = (key: string) => key in chatFlows || RUNTIME_TOKENS.has(key);

      for (const [chip, target] of Object.entries(chipToFlowKey)) {
        if (!known(target)) problems.push(`chip "${chip}" → missing turn "${target}"`);
      }
      for (const key of [...askTurnSequence, ...signalSequence, ...(actionTurnKey ? [actionTurnKey] : [])]) {
        if (!known(key)) problems.push(`sequence names missing turn "${key}"`);
      }
      const offered = new Set<string>(manifest.ui.initialChips);
      for (const flow of Object.values(chatFlows)) {
        for (const chip of (flow as { suggested_chips?: string[] }).suggested_chips || []) offered.add(chip);
      }
      for (const chip of Object.values(manifest.ui.signalToChip)) offered.add(chip);
      const actionFlow = actionTurnKey ? (chatFlows[actionTurnKey] as { post_confirm_response?: Record<string, string> }) : undefined;
      for (const [actionId, cfg] of Object.entries(manifest.flows.actionConfirmMap ?? {})) {
        const { responseKey, nextChips = [] } = cfg as { responseKey: string; nextChips?: string[] };
        if (!actionFlow?.post_confirm_response?.[responseKey]) {
          problems.push(`action "${actionId}" has no post_confirm_response["${responseKey}"] on "${actionTurnKey}" — Confirm does nothing`);
        }
        for (const chip of nextChips) offered.add(chip);
      }
      if (!chatFlows.__default__) problems.push('no __default__ turn — an unmatched typed question gets no answer');
      for (const chip of offered) {
        if (resolve(chip) !== null) continue;
        // Say where a click actually goes today, so the snapshot is a bug list.
        const actual = resolveFlowKey(manifest.flows, chip).flowKey;
        problems.push(`chip "${chip}" has no route; a click lands on ${actual ?? 'nothing'}`);
      }
      expect(problems).toMatchSnapshot();
    },
    20_000,
  );
});
