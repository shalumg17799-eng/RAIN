/**
 * Recorded responses: today's scripted flows, carrying the components each
 * turn draws as contract data instead of as JSX in a persona's switchboard.
 *
 *   flows: withComponents(baseFlows, {
 *     signal_turn: [signalCardSpec(signals, 'SIG-1', { showAction: true })],
 *   })
 *
 * The map is exactly what `POST /ask` will return in `components[]`; when the
 * backend arrives it replaces this data, and the persona's code does not
 * change. The fixtures stay the single source of each figure — the specs are
 * built from them at load, not copied into them.
 */
import type { ChatFlowConfig, UiComponentSpec } from '../types';
import type { ContractSpec } from './spec';
import { normalizeSignal } from './signal';

/** A copy of `flows` with `specs` prepended to each named turn's components. */
export function withComponents(flows: ChatFlowConfig, byFlow: Record<string, ContractSpec[]>): ChatFlowConfig {
  const chatFlows = { ...flows.chatFlows };
  for (const [flowKey, specs] of Object.entries(byFlow)) {
    const flow = chatFlows[flowKey];
    if (!flow) throw new Error(`withComponents: no turn "${flowKey}" to attach components to`);
    const existing = Array.isArray(flow.ui_components_to_render) ? flow.ui_components_to_render : [];
    chatFlows[flowKey] = { ...flow, ui_components_to_render: [...(specs as unknown as UiComponentSpec[]), ...existing] };
  }
  return { ...flows, chatFlows };
}

/** A `signal_card` spec for one signal of a persona's list, in the standard shape. */
export function signalCardSpec(
  signals: Array<Record<string, unknown>>,
  id: string,
  options: { showAction?: boolean; compact?: boolean; tone?: 'urgent' | 'calm' } = {},
): ContractSpec {
  const raw = signals.find((s) => s.id === id);
  if (!raw) throw new Error(`signalCardSpec: no signal "${id}"`);
  return { type: 'signal_card', version: 1, props: { signal: normalizeSignal(raw), ...options } };
}
