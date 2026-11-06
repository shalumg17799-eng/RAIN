/**
 * The six endpoints of the Ultra API (v1) — the contract the backend builds.
 * Field-by-field reference: docs/standard/api.md.
 */
import type { AiTurn } from '../contract/aiTurn';
import type { StandardSignal } from '../contract/signal';
import type { Trend } from '../contract/status';

export interface PersonaRef {
  clientId: string;
  personaId: string;
}

/** GET /context — what the shell needs to draw a tenant and persona. */
export interface ContextResponse {
  client: {
    id: string;
    marketId: string;
    name: string;
    shortName: string;
    logo: string;
    primaryColor: string;
    navLabels?: Record<string, string>;
  };
  persona: {
    id: string;
    name: string;
    initials: string;
    role: string;
    layout: 'split' | 'inline' | 'full';
    capabilities: string[];
    navSlots?: string[];
  };
  /** Every persona the client offers, in display order (the switcher). */
  personas: Array<{ id: string; name: string; role: string }>;
  /** The Data Sources page. */
  dataSources: Array<{ id: string; name?: string; [key: string]: unknown }>;
}

/** One KPI tile on the home view. Icons are registry ids, never components. */
export interface KpiTile {
  id: string;
  label: string;
  value: string;
  trendText?: string;
  trend?: Trend;
  icon?: string;
  /** The chip a click on the tile sends. */
  chip?: string;
}

/** GET /briefing — the home view. */
export interface BriefingResponse {
  greeting: AiTurn;
  signals: StandardSignal[];
  kpis: KpiTile[];
  /** Starter chips under the greeting. */
  chips: string[];
}

/** POST /ask */
export interface AskRequest extends PersonaRef {
  /** The chip label or typed question. */
  input: string;
}

/** POST /actions/{id} */
export interface ActionRequest extends PersonaRef {
  actionId: string;
}

export interface ActionResponse {
  /** The confirmation message, as a turn. */
  turn: AiTurn;
}

/** The API the app talks to, whatever serves it. */
export interface UltraApi {
  getContext(ref: PersonaRef): Promise<ContextResponse>;
  getBriefing(ref: PersonaRef): Promise<BriefingResponse>;
  ask(req: AskRequest): Promise<AiTurn>;
  runAction(req: ActionRequest): Promise<ActionResponse>;
  getCatalog(): Promise<unknown>;
  /** POST /tts is served as a cacheable GET today; this builds its URL. */
  ttsUrl(params: { slide: string; tenant?: string; persona?: string }): string;
}
