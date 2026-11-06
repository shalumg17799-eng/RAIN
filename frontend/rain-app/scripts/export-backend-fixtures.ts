/**
 * Export the recorded API payloads as JSON fixtures for the Python backend —
 * `npm run fixtures:backend` → `rain-api/fixtures/ultra_v3/`.
 *
 * One file per persona: the /context and /briefing responses, every turn by
 * flowKey (built through the same `toAiTurn` + answers path the recorded
 * adapter uses), and the matching tables (`chipToFlowKey`, per-flow
 * user_query/corpus) that the backend's port of the chatFlowEngine ladder
 * reads. Plus catalog.json. Re-run after changing a persona contract,
 * answers, or the catalog; the backend picks the new files up on restart.
 */
import { mkdirSync, writeFileSync, copyFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRecordedApi } from '../src/core/api/recorded';
import { getMarkets } from '../src/core/runtime/registry';
import { toAiTurn, type AiTurn } from '../src/core/contract/aiTurn';
import type { ChatFlow, PersonaManifest } from '../src/core/types';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, '../../../rain-api/fixtures/ultra_v3');
const api = createRecordedApi();

/** Same composition the recorded adapter applies (recorded.ts `withAnswer`). */
function withAnswer(m: PersonaManifest, flowKey: string, turn: AiTurn): AiTurn {
  const flow = m.flows.chatFlows[flowKey] as ChatFlow | undefined;
  const answer = m.answers?.({ flowKey, role: 'ai', uiComponents: flow?.ui_components_to_render ?? [] }, m.signals ?? []) ?? [];
  return answer.length ? { ...turn, components: [...turn.components, ...answer] } : turn;
}

mkdirSync(OUT, { recursive: true });
let count = 0;
for (const market of getMarkets()) {
  for (const client of market.clients) {
    for (const p of client.personas) {
      const ref = { clientId: client.id, personaId: p.id };
      const manifest = (await p.load()).default as PersonaManifest;
      const turns: Record<string, AiTurn> = {};
      const flowsMeta: Record<string, { user_query: string; corpus: string }> = {};
      for (const [key, raw] of Object.entries(manifest.flows.chatFlows)) {
        const flow = raw as ChatFlow;
        turns[key] = withAnswer(manifest, key, toAiTurn(key, flow));
        const q = String(flow.user_query ?? '');
        flowsMeta[key] = {
          user_query: q,
          corpus: `${q} ${flow.ai_message ?? ''} ${flow.ai_response ?? ''}`.toLowerCase(),
        };
      }
      const fixture = {
        context: await api.getContext(ref),
        briefing: await api.getBriefing(ref),
        turns,
        match: {
          chipToFlowKey: manifest.flows.chipToFlowKey,
          strictMatch: manifest.flows.strictMatch === true,
          signalSequence: manifest.flows.signalSequence ?? [],
          flows: flowsMeta,
        },
      };
      writeFileSync(join(OUT, `${p.id}.json`), JSON.stringify(fixture, null, 1));
      console.log(`wrote ${p.id}.json (${Object.keys(turns).length} turns)`);
      count += 1;
    }
  }
}
copyFileSync(join(HERE, '../docs/catalog/catalog.json'), join(OUT, 'catalog.json'));
console.log(`wrote catalog.json — ${count} personas exported to ${OUT}`);
