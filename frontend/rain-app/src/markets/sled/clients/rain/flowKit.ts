/**
 * How a RAIN persona's contract becomes its conversation: every step a turn,
 * every `asks` label a route (with loose matching for typed questions), the
 * golden path from each step's `next`, capability triggers for Use Case A,
 * and the hooks that run a step's store action and launch its workbench.
 * Tenant-owned: nothing outside this client imports it.
 */
import type { ChatFlowConfig } from '@core/types';
import type { RainContract } from '@/data/rain/_shared/contract';
import { requestLaunch, runAction } from '@/components/rain/shell/store';

/** Typed questions match with or without punctuation, in any case. */
export const loose = (t: string) => t.toLowerCase().replace(/[?.!,':]/g, '').replace(/\s+/g, ' ').trim();

const TRIGGER_BY_CAPABILITY: Record<string, string> = {
  'Proactive Intelligence': 'briefing',
  'Converged Conversation': 'converged',
  'Friction Observability': 'friction',
  'Predictive Intelligence': 'predictive',
  'Anomaly Detection': 'anomaly',
  'Automated Action': 'action',
};

export interface RainFlowSet {
  flows: ChatFlowConfig;
  greetingFlowKey: string;
  goldenPathChip: Record<string, string>;
  flowKeyToCapabilityTrigger: Record<string, string>;
}

export function buildFlows(contract: RainContract, useCase: 'A' | 'B'): RainFlowSet {
  const entries = Object.entries(contract.steps);
  const greetingFlowKey = entries.find(([k]) => k.endsWith('_brief'))![0];

  const chatFlows: ChatFlowConfig['chatFlows'] = {};
  const routes: Record<string, string> = {};
  for (const [key, s] of entries) {
    chatFlows[key] = {
      user_query: s.asks?.[0],
      ai_message: s.ai,
      data_sources_used: s.sources,
      suggested_chips: s.chips,
      confidence: key === '__default__' ? 60 : 92,
      ...(useCase === 'A' && s.capability ? { capability: s.capability } : {}),
    };
    for (const label of s.asks ?? []) routes[label] = key;
  }

  const chipToFlowKey: Record<string, string> = {};
  for (const [label, key] of Object.entries(routes)) {
    chipToFlowKey[label] = key;
    chipToFlowKey[label.toLowerCase()] = key;
    chipToFlowKey[loose(label)] = key;
  }
  const byLoose = new Map(Object.entries(routes).map(([label, key]) => [loose(label), key]));

  const goldenPathChip: Record<string, string> = {};
  for (const [key, s] of entries) if (s.next) goldenPathChip[key] = s.next;

  const flowKeyToCapabilityTrigger: Record<string, string> =
    useCase === 'A'
      ? Object.fromEntries(entries.filter(([k, s]) => !k.startsWith('__') && s.capability && TRIGGER_BY_CAPABILITY[s.capability]).map(([k, s]) => [k, TRIGGER_BY_CAPABILITY[s.capability!]]))
      : {};

  const askTurnSequence = entries.filter(([, s]) => s.step && s.step > 1).sort((a, b) => a[1].step! - b[1].step!).map(([k]) => k);

  const flows: ChatFlowConfig = {
    chatFlows,
    chipToFlowKey,
    askTurnSequence,
    signalSequence: [],
    strictMatch: true,
    // The greeting lands at once, so the longer opening list (briefing chips
    // plus suggested questions) never shows as a row of buttons before it.
    instantGreeting: true,
    matchUtterance: (input: string) => byLoose.get(loose(input)) ?? null,
    onFlowEnter: (flowKey) => {
      const s = contract.steps[flowKey];
      if (!s) return;
      runAction(s.action);
      if (s.launch) requestLaunch(flowKey, s.launch);
    },
  };
  return { flows, greetingFlowKey, goldenPathChip, flowKeyToCapabilityTrigger };
}
