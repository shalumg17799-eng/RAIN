/**
 * The recorded adapter: the API answered from today's scripted manifests.
 *
 * This is how demos run with no backend, and it is the reference the backend
 * is tested against — the mock server (`npm run mock-api`) serves exactly
 * these responses over HTTP. Every response is built through the same
 * contract functions (`toAiTurn`, `normalizeSignal`), so a recorded response
 * and a live one have one shape.
 */
import { getClientPersonas, findClient, getPersonaModule } from '../runtime/registry';
import { resolveFlowKey, resolveNextSignal, NEXT_SIGNAL_TOKEN, DEFAULT_FLOW_KEY } from '../engine/chatFlowEngine';
import { toAiTurn, type AiTurn } from '../contract/aiTurn';
import { normalizeSignal } from '../contract/signal';
import { iconIdOf } from '../contract/icons';
import { listCatalog } from '../catalog/registry';
import type { ChatFlow, PersonaManifest } from '../types';
import type { ActionRequest, ActionResponse, AskRequest, BriefingResponse, ContextResponse, PersonaRef, UltraApi } from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function loadManifest({ clientId, personaId }: PersonaRef): Promise<PersonaManifest> {
  const mod = getPersonaModule(clientId, personaId);
  if (!mod) throw new ApiError(404, `No persona "${personaId}" for client "${clientId}"`);
  return (await mod.load()).default;
}

/** Signal-walkthrough position per persona, as a live session would keep it. */
const signalCursor = new Map<string, number>();

/** A turn plus the persona's recorded answer components, exactly as the chat draws them. */
function withAnswer(m: PersonaManifest, flowKey: string, turn: AiTurn): AiTurn {
  const flow = m.flows.chatFlows[flowKey] as ChatFlow | undefined;
  const answer = m.answers?.({ flowKey, role: 'ai', uiComponents: flow?.ui_components_to_render ?? [] }, m.signals ?? []) ?? [];
  return answer.length ? { ...turn, components: [...turn.components, ...answer] } : turn;
}

export function createRecordedApi(): UltraApi {
  return {
    async getContext(ref) {
      const found = findClient(ref.clientId);
      if (!found) throw new ApiError(404, `No client "${ref.clientId}"`);
      const m = await loadManifest(ref);
      const { client } = found;
      const res: ContextResponse = {
        client: {
          id: client.id,
          marketId: client.marketId,
          name: client.branding.name,
          shortName: client.branding.shortName,
          logo: client.branding.logo,
          primaryColor: client.branding.primaryColor,
          ...(client.branding.navLabels ? { navLabels: client.branding.navLabels as Record<string, string> } : {}),
        },
        persona: {
          id: m.id,
          name: m.identity.name,
          initials: m.identity.initials,
          role: m.identity.role,
          layout: m.layout,
          capabilities: [...m.capabilities],
          ...(m.features?.navSlots ? { navSlots: [...m.features.navSlots] } : {}),
        },
        personas: getClientPersonas(ref.clientId).map((p) => ({ id: p.id, name: p.identity.name, role: p.identity.role })),
        dataSources: m.dataSources as ContextResponse['dataSources'],
      };
      return res;
    },

    async getBriefing(ref) {
      const m = await loadManifest(ref);
      // Same rewrite the chat applies when it opens on the greeting (a persona's
      // `resolveFlowKey` may route it to a variant, e.g. the Comptroller's v3 morning).
      const rewritten = m.flows.resolveFlowKey?.(m.ui.greetingFlowKey);
      const greetingKey = rewritten && m.flows.chatFlows[rewritten] ? rewritten : m.ui.greetingFlowKey;
      const res: BriefingResponse = {
        greeting: withAnswer(m, greetingKey, toAiTurn(greetingKey, m.flows.chatFlows[greetingKey] as ChatFlow)),
        signals: m.signals.map((s) => normalizeSignal(s as Record<string, unknown>)),
        kpis: m.ui.stats.map((t) => ({
          id: t.id,
          label: t.label,
          value: t.value,
          ...(t.trend ? { trendText: t.trend } : {}),
          ...(iconIdOf(t.icon) ? { icon: iconIdOf(t.icon) } : {}),
          ...(t.chipText ? { chip: t.chipText } : {}),
        })),
        chips: [...m.ui.initialChips],
      };
      signalCursor.set(`${ref.clientId}/${ref.personaId}`, 0);
      return res;
    },

    async ask(req: AskRequest) {
      const m = await loadManifest(req);
      const cursorKey = `${req.clientId}/${req.personaId}`;
      let flowKey: string | null;
      if (req.input === 'Next signal' || req.input === 'Yes, walk me through them') {
        const i = req.input === 'Yes, walk me through them' ? 0 : (signalCursor.get(cursorKey) ?? 0);
        flowKey = resolveNextSignal(m.flows, i);
        signalCursor.set(cursorKey, i + 1);
      } else {
        const r = resolveFlowKey(m.flows, req.input);
        flowKey = r.flowKey === NEXT_SIGNAL_TOKEN ? resolveNextSignal(m.flows, signalCursor.get(cursorKey) ?? 0) : r.flowKey;
      }
      if (!flowKey) flowKey = m.flows.chatFlows[DEFAULT_FLOW_KEY] ? DEFAULT_FLOW_KEY : null;
      if (!flowKey) throw new ApiError(422, `No answer for "${req.input}"`);
      const rewritten = m.flows.resolveFlowKey?.(flowKey);
      const key = rewritten && m.flows.chatFlows[rewritten] ? rewritten : flowKey;
      return withAnswer(m, key, toAiTurn(key, m.flows.chatFlows[key] as ChatFlow));
    },

    async runAction(req: ActionRequest): Promise<ActionResponse> {
      const m = await loadManifest(req);
      const { actionTurnKey, actionConfirmMap = {} } = m.flows;
      const flow = actionTurnKey ? (m.flows.chatFlows[actionTurnKey] as ChatFlow) : undefined;
      const confirm = actionConfirmMap[req.actionId];
      if (!flow?.post_confirm_response || !confirm) throw new ApiError(404, `No action "${req.actionId}"`);
      return {
        turn: {
          id: `action_confirm_${req.actionId}`,
          text: flow.post_confirm_response[confirm.responseKey] || '',
          citations: [],
          components: [],
          chips: confirm.nextChips || [],
        },
      };
    },

    async getCatalog() {
      return listCatalog().map((e) => ({ type: e.type, version: e.version, tier: e.tier, title: e.title, description: e.description, example: e.example }));
    },

    ttsUrl({ slide, tenant, persona }) {
      const q = new URLSearchParams({ slide });
      if (tenant) q.set('tenant', tenant);
      if (persona) q.set('persona', persona);
      return `/api/tts?${q.toString()}`;
    },
  };
}
