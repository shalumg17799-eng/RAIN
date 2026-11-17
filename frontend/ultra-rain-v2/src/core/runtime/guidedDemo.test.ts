/**
 * Every persona's guided demo (manifest `guidedDemo`) can actually be played:
 * replayed through the persona's own conversation, each chip a script clicks
 * on the chat screen is offered on the turn on screen at that moment, the way
 * DemoRunner finds it (a chip containing the step's text), and a typed
 * question lands on a turn. Clicks on other
 * pages target that page's own content (a risk card on /risk) and are not
 * checked here.
 *
 * Scripts used to drift silently: a reworded chip made the runner wait and
 * skip the step with no error anywhere. This test fails instead.
 */
import { describe, it, expect } from 'vitest';
import { getMarkets } from '@core/runtime/registry';
import { resolveFlowKey, NEXT_SIGNAL_TOKEN } from '@core/engine/chatFlowEngine';
import type { PersonaManifest } from '@core/types';

type Flow = { suggested_chips?: string[] };

const CHAT_PATHS = /^\/(ask)?(\?.*)?$/;

/** The flow a chip leads to, following the live chat's signal walk. */
function land(m: PersonaManifest, chip: string, signalIndex: number): { flowKey: string | null; signalIndex: number } {
  const seq = m.flows.signalSequence ?? [];
  if (chip === 'Next signal' || chip === 'Yes, walk me through them') {
    const idx = chip === 'Yes, walk me through them' ? 0 : signalIndex;
    return { flowKey: seq[idx] ?? null, signalIndex: idx + 1 };
  }
  const { flowKey } = resolveFlowKey(m.flows, chip);
  if (flowKey === NEXT_SIGNAL_TOKEN) return { flowKey: seq[signalIndex] ?? null, signalIndex: signalIndex + 1 };
  const sig = flowKey ? seq.indexOf(flowKey) : -1;
  return { flowKey, signalIndex: sig >= 0 ? sig + 1 : signalIndex };
}

const personas = getMarkets().flatMap((market) => market.clients.flatMap((client) => client.personas.map((p) => ({ client: client.id, p }))));

describe('guided demos follow the current conversation', () => {
  it.each(personas.map(({ client, p }) => [`${client}/${p.id}`, p] as const))('%s', async (_name, p) => {
    const m = (await p.load()).default as PersonaManifest;
    if (!m.guidedDemo) return;
    const flows = m.flows.chatFlows as Record<string, Flow>;
    const offers = (chips: string[], partial: string) => chips.find((c) => c.toLowerCase().includes(partial.toLowerCase()));

    let onChat = true;
    let onScreen = m.ui.greetingFlowKey;
    let signalIndex = 0;
    for (const step of m.guidedDemo.steps) {
      for (const action of step.actions) {
        if (action.type === 'navigate') {
          onChat = CHAT_PATHS.test(action.path);
          if (onChat) { onScreen = m.ui.greetingFlowKey; signalIndex = 0; }
        }
        if (action.type === 'submitQuery' && onChat) {
          const typed = land(m, action.query, signalIndex);
          expect(typed.flowKey, `"${step.label}": typing "${action.query}" leads nowhere`).toBeTruthy();
          onScreen = typed.flowKey as string;
          signalIndex = typed.signalIndex;
          continue;
        }
        if (action.type !== 'clickChip') continue;
        if (!onChat) continue;
        const chip = offers(flows[onScreen]?.suggested_chips ?? [], action.partial);
        expect(chip, `"${step.label}": ${onScreen} offers no chip containing "${action.partial}"`).toBeTruthy();
        const next = land(m, chip as string, signalIndex);
        expect(next.flowKey, `"${step.label}": "${chip}" leads nowhere`).toBeTruthy();
        onScreen = next.flowKey as string;
        signalIndex = next.signalIndex;
      }
    }
  });
});
