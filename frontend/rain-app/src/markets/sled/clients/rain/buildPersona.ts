/**
 * The one shape every RAIN operator persona's manifest takes. A persona is its
 * contract (`data/rain/<persona>.json`) plus identity and a few words of copy.
 * Use Case A personas land on an insight briefing (three signal cards, KPI
 * tiles, guided conversation, capability tags); Use Case B personas land on a
 * task briefing with no signals and no capability tags (spec "Delineation").
 */
import type { ComponentType } from 'react';
import type { CapabilityId, DataSource, NavKey, PersonaIdentity, PersonaManifest, PersonaNotification, Signal, StatTile } from '@core/types';
import type { PersonaKey } from '@/data/rain/_shared/constants';
import { PERSONAS } from '@/data/rain/_shared/constants';
import type { RainContract } from '@/data/rain/_shared/contract';
import { WORKBENCHES } from '@/data/rain/_shared/contract';
import { CAPABILITY_CALLOUTS, CAPABILITY_DIAGRAMS } from '@/data/rain/_shared/capabilities';
import { ASK_EVENT } from '@/components/rain/shell/store';
import RainFooter from '@/components/rain/shell/RainFooter';
import RainSignals from '@/components/rain/shell/RainSignals';
import RainKpiRow from '@/components/rain/shell/RainKpiRow';
import RainDataSources from '@/components/rain/workbenches/RainDataSources';
import { buildFlows } from './flowKit';
import { RAIN_CATALOG, rainAnswers } from './answers';

export interface RainPersonaSpec {
  key: PersonaKey;
  identity: PersonaIdentity;
  contract: RainContract;
  inputPlaceholder: string;
  greetingSubtitle: string;
  notifications?: PersonaNotification[];
  /** The Data Sources page and GET /context: every persona reads the same foundation. */
  dataSources: DataSource[];
}

const A_CAPABILITIES: CapabilityId[] = ['Proactive Intelligence', 'Converged Conversation', 'Anomaly Detection', 'Predictive Intelligence', 'Friction Observability', 'Automated Action'];

/** Every type a list of specs draws, including inside grid and stack. */
function typesIn(specs: Array<{ type: string; props?: unknown }> | undefined, out = new Set<string>()): Set<string> {
  for (const s of specs ?? []) {
    out.add(s.type);
    const children = (s.props as { children?: Array<{ type: string; props?: unknown }> } | undefined)?.children;
    if (Array.isArray(children)) typesIn(children, out);
  }
  return out;
}

export function buildRainPersona(p: RainPersonaSpec): PersonaManifest {
  const c = p.contract;
  const useCase: 'A' | 'B' = c.signals.length ? 'A' : 'B';
  const set = buildFlows(c, useCase);
  const drawn = new Set<string>();
  for (const key of Object.keys(c.steps)) typesIn(rainAnswers(c, key), drawn);
  const catalog = RAIN_CATALOG.filter((e) => drawn.has(e.type));

  const signals: Signal[] = c.signals.map((s) => ({
    id: s.id,
    title: s.title,
    severity: s.severity,
    impact: s.severity === 'critical' ? 'high' : 'medium',
    description: s.description,
    metric_text: s.metric,
    sources: s.sources,
    primary: s.primary,
  }));
  const stats: StatTile[] = c.kpis.map((k) => ({
    id: k.id,
    label: k.label,
    value: k.value,
    trend: [k.detail, k.source].filter(Boolean).join(' · '),
    icon: k.icon,
    tone: k.tone,
    chipText: k.chip ?? null,
  }));
  const navSlots: NavKey[] = ['ask', ...c.workbenches.map((w) => WORKBENCHES[w.id].nav)];

  return {
    id: PERSONAS[p.key],
    clientId: 'rain',
    marketId: 'sled',
    identity: p.identity,
    capabilities: useCase === 'A' ? A_CAPABILITIES : ['Converged Conversation', 'Automated Action'],
    flows: set.flows,
    signals,
    dataSources: p.dataSources,
    layout: 'inline',
    capabilityDiagrams: useCase === 'A' ? CAPABILITY_DIAGRAMS : undefined,
    pages: { dataSources: RainDataSources },
    features: {
      askEvent: ASK_EVENT,
      navSlots,
      wideInlineComponents: true,
      topAlignedInitial: true,
      persistConversation: true,
    },
    notifications: p.notifications,
    ui: {
      greetingFlowKey: set.greetingFlowKey,
      // The briefing's chips, then the persona's suggested questions: they appear
      // in the question box's suggestion list when it is focused (no extra row).
      initialChips: [...new Set([...c.steps[set.greetingFlowKey].chips, ...c.queries])],
      goldenPathChip: set.goldenPathChip,
      flowKeyToCapabilityTrigger: set.flowKeyToCapabilityTrigger,
      capabilityCallouts: useCase === 'A' ? CAPABILITY_CALLOUTS : [],
      stats,
      signalToChip: Object.fromEntries(c.signals.map((s) => [s.id, s.chip])),
      inputPlaceholder: p.inputPlaceholder,
      greetingLabel: 'Good morning',
      greetingSubtitle: p.greetingSubtitle,
      contentMaxWidth: 'max-w-6xl',
    },
    workspaceFooter: RainFooter,
    signalsComponent: RainSignals as ComponentType<Record<string, unknown>>,
    statsComponent: RainKpiRow as ComponentType<Record<string, unknown>>,
    answers: (msg) => rainAnswers(c, msg.flowKey, msg.id as string | number | undefined),
    catalog,
  };
}
