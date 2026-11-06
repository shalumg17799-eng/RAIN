/**
 * The page net — every shared page and capability diagram, for every persona.
 *
 * Companion to the card net (personaCards.test.jsx). The shared screens
 * (Member Journey, Risk Signals, Data Sources, Governance) and the six
 * capability deep-dive diagrams draw different content per persona; moving
 * that per-persona content out of shared code and behind manifest fields must
 * not change a byte, and this snapshot is the proof. A changed hash names the
 * persona and the page.
 *
 * Lazy pages render their Suspense fallback under the static renderer, so a
 * page that hands off to a lazy tenant page is fingerprinted as that handoff —
 * still enough to catch a persona being routed to the wrong page.
 */
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { createHash } from 'node:crypto';
import { renderToStaticMarkup } from 'react-dom/server';
import { getMarkets } from './registry';
import { PersonaHarness } from '@/test/harness';
import { settleLazy } from '@/test/eagerLazy';
import { loadManifest } from './manifestCache';
import { CLIENTS, DEFAULT_CLIENT_ID } from '@/config/clients';
import MemberJourney from '@/screens/MemberJourney';
import RiskSignals from '@/screens/RiskSignals';
import DataSources from '@/screens/DataSources';
import Governance from '@/screens/Governance';
import MyReports from '@/screens/MyReports';
import AgentInventory from '@/screens/AgentInventory';
import AgentObservability from '@/screens/AgentObservability';
import ProactiveIntelligenceDiagram from '@/components/capabilities/ProactiveIntelligenceDiagram';
import TalkToDataDiagram from '@/components/capabilities/TalkToDataDiagram';
import BehavioralSegmentationDiagram from '@/components/capabilities/BehavioralSegmentationDiagram';
import PredictiveIntelligenceDiagram from '@/components/capabilities/PredictiveIntelligenceDiagram';
import ActionExecutionDiagram from '@/components/capabilities/ActionExecutionDiagram';
import AnomalyDetectionDiagram from '@/components/capabilities/AnomalyDetectionDiagram';
import DataOverviewBar from '@/components/cards/DataOverviewBar';

// Lazy boundaries resolve before anything is drawn (see test/eagerLazy.js), so
// a fingerprint never depends on how fast a dynamic import loaded.
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  const { createEagerLazy } = await import('@/test/eagerLazy');
  return { ...actual, lazy: createEagerLazy(actual.createElement) };
});
vi.mock('react-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, createPortal: (children) => children };
});

const PAGES = {
  journey: ['/journey', MemberJourney],
  risk: ['/risk', RiskSignals],
  dataSources: ['/data-sources', DataSources],
  governance: ['/governance', Governance],
  myReports: ['/my-reports', MyReports],
  agentInventory: ['/agent-inventory', AgentInventory],
  agentObservability: ['/agent-observability', AgentObservability],
  // Diagrams are drawn as the capability modal draws them: with the persona's
  // `capabilityDiagrams` entry for that diagram as `content`, and the client's
  // short name.
  proactiveDiagram: ['/ask', ProactiveIntelligenceDiagram, 'proactive'],
  talkToDataDiagram: ['/ask', TalkToDataDiagram, 'converged'],
  segmentationDiagram: ['/ask', BehavioralSegmentationDiagram, 'friction'],
  predictiveDiagram: ['/ask', PredictiveIntelligenceDiagram, 'predictive'],
  actionDiagram: ['/ask', ActionExecutionDiagram, 'action'],
  anomalyDiagram: ['/ask', AnomalyDetectionDiagram, 'anomaly'],
};

const entries = getMarkets().flatMap((market) =>
  market.clients.flatMap((client) => client.personas.map((persona) => ({ client, persona }))),
);

// Class order never changes what is drawn, so it is normalised away: a page
// rebuilt from shared parts may list the same utilities in another order.
const normaliseClasses = (html) =>
  html.replace(/class="([^"]*)"/g, (_m, c) => `class="${c.split(/\s+/).filter(Boolean).sort().join(' ')}"`);
const hash = (s) => createHash('sha1').update(normaliseClasses(s)).digest('hex').slice(0, 10);

describe('shared pages render identically per persona', () => {
  beforeAll(() => {
    vi.useFakeTimers({ now: new Date('2026-10-14T13:30:00Z'), toFake: ['Date'] });
    let s = 7;
    vi.spyOn(Math, 'random').mockImplementation(() => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; });
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterAll(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

  it.each(entries.map((e) => [`${e.client.id}/${e.persona.id}`, e]))('%s', async (_label, { client, persona }) => {
    // As after visiting /ask: the persona's manifest is loaded, so a shared
    // page can hand off to the persona's own page on the first render.
    const manifest = await loadManifest(persona);
    await settleLazy();
    const fingerprint = {};
    for (const [name, [path, Page, diagramKind]] of Object.entries(PAGES)) {
      const props = diagramKind ? { content: manifest.capabilityDiagrams?.[diagramKind], clientName: (CLIENTS[client.id] ?? CLIENTS[DEFAULT_CLIENT_ID]).shortName } : {};
      sessionStorage.clear();
      localStorage.clear();
      try {
        const html = renderToStaticMarkup(
          <PersonaHarness clientId={client.id} personaId={persona.id} path={path}><Page {...props} /></PersonaHarness>,
        );
        fingerprint[name] = hash(html);
      } catch (err) {
        fingerprint[name] = `!error ${String(err?.message || err).split('\n')[0].slice(0, 80)}`;
      }
    }
    // The KPI tiles of the home view, as the workspace draws them.
    {
      const Stats = manifest.statsComponent || DataOverviewBar;
      try {
        const html = renderToStaticMarkup(
          <PersonaHarness clientId={client.id} personaId={persona.id}><Stats visible stats={manifest.ui.stats} onStatClick={() => {}} /></PersonaHarness>,
        );
        fingerprint.stats = hash(html);
      } catch (err) {
        fingerprint.stats = `!error ${String(err?.message || err).split('\n')[0].slice(0, 80)}`;
      }
    }
    // The workspace's right-hand context panel, turn by turn.
    for (const [turn, Panel] of Object.entries(manifest.contextPanel ?? {})) {
      if (typeof Panel !== 'function' && typeof Panel !== 'object') continue;
      try {
        const html = renderToStaticMarkup(
          <PersonaHarness clientId={client.id} personaId={persona.id}><Panel /></PersonaHarness>,
        );
        fingerprint[`contextPanel${turn}`] = hash(html);
      } catch (err) {
        fingerprint[`contextPanel${turn}`] = `!error ${String(err?.message || err).split('\n')[0].slice(0, 80)}`;
      }
    }
    expect(fingerprint).toMatchSnapshot();
  }, 60_000);
});
