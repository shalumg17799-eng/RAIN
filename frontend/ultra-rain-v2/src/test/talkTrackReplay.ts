/**
 * Test helper: replays a talk track's CLICK lines the way the live chat does.
 *
 * Mirrors `handleChipClick` in core/engine/useManifestChat.js. "Yes, walk me
 * through them" always opens the first signal and "Next signal" the next one,
 * whatever the chip map says. Any other chip goes through the engine's
 * resolver, and landing on a signal moves the signal index past it. A test that
 * resolved every chip through `chipToFlowKey` alone would pass on a path the
 * demo cannot actually walk.
 */
import { expect } from 'vitest';
import type { PersonaManifest } from '@core/types';
import { resolveFlowKey, NEXT_SIGNAL_TOKEN } from '@core/engine/chatFlowEngine';

type Flow = { suggested_chips?: string[] };
export type TalkTrackStep = [click: string, lands: string];

function click(m: PersonaManifest, chip: string, signalIndex: number): { flowKey: string | null; signalIndex: number } {
  const seq = m.flows.signalSequence;
  if (chip === 'Next signal' || chip === 'Yes, walk me through them') {
    const idx = chip === 'Yes, walk me through them' ? 0 : signalIndex;
    return { flowKey: seq[idx] ?? null, signalIndex: idx + 1 };
  }
  const { flowKey } = resolveFlowKey(m.flows, chip);
  if (flowKey === NEXT_SIGNAL_TOKEN) return { flowKey: seq[signalIndex] ?? null, signalIndex: signalIndex + 1 };
  const sig = flowKey ? seq.indexOf(flowKey) : -1;
  return { flowKey, signalIndex: sig >= 0 ? sig + 1 : signalIndex };
}

/**
 * From the greeting, each CLICK must be offered on the turn on screen, be the
 * highlighted chip, and land where the talk track says; the highlight must stop
 * where the talk track stops.
 */
export function expectTalkTrack(m: PersonaManifest, steps: TalkTrackStep[]): void {
  const chatFlows = m.flows.chatFlows as Record<string, Flow>;
  let onScreen = m.ui.greetingFlowKey;
  let signalIndex = 0;
  for (const [chip, lands] of steps) {
    expect(chatFlows[onScreen]?.suggested_chips, `${onScreen} does not offer "${chip}"`).toContain(chip);
    expect(m.ui.goldenPathChip[onScreen], `${onScreen} highlights the wrong chip`).toBe(chip);
    const next = click(m, chip, signalIndex);
    expect(next.flowKey, `"${chip}" lands in the wrong place`).toBe(lands);
    onScreen = lands;
    signalIndex = next.signalIndex;
  }
  expect(m.ui.goldenPathChip[onScreen], `the highlight runs past the end of the talk track at ${onScreen}`).toBeUndefined();
}
