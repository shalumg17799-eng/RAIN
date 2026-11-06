/**
 * One response shape for every AI turn (the Oct 21 contract).
 *
 * Scripted today, live tomorrow: the backend's `POST /ask` returns exactly
 * this, and today's `chatFlows` fixtures are read into it by `toAiTurn()` as
 * recorded responses. The UI draws `components[]` through the catalog and
 * never needs to know which one produced the turn.
 */
import { z } from 'zod';
import type { ChatFlow } from '../types';
import { isContractSpec } from './spec';

export { isContractSpec, contractComponents } from './spec';

/** One thing to draw: a catalog type, its contract version, and its props. */
export const componentSpecSchema = z.object({
  /** snake_case catalog type, e.g. `trend_chart`. */
  type: z.string().min(1),
  /** Contract version of that type; a changed shape is a new version or type. */
  version: z.number().int().positive().default(1),
  /** Props that satisfy the type's catalog schema. */
  props: z.record(z.string(), z.unknown()).default({}),
});
export type ComponentSpec = z.infer<typeof componentSpecSchema>;

export const aiTurnSchema = z.object({
  /** The turn's id: today the flowKey, later the API's turn id. */
  id: z.string().min(1),
  /** The answer in words. */
  text: z.string(),
  /** Data-source ids or names the answer cites. */
  citations: z.array(z.string()).default([]),
  /** What to draw under the answer, in order. */
  components: z.array(componentSpecSchema).default([]),
  /** Suggested follow-ups. */
  chips: z.array(z.string()).default([]),
  /** Capability tag, e.g. "Predictive Intelligence". */
  capability: z.string().optional(),
  /** 0–100. */
  confidence: z.number().optional(),
});
export type AiTurn = z.infer<typeof aiTurnSchema>;

/** Read one scripted flow into the response contract (a recorded response). */
export function toAiTurn(flowKey: string, flow: ChatFlow): AiTurn {
  const legacy = Array.isArray(flow.ui_components_to_render) ? flow.ui_components_to_render : [];
  const components: ComponentSpec[] = legacy.map((entry) => {
    if (isContractSpec(entry)) return componentSpecSchema.parse(entry);
    const { type, ...rest } = entry as { type?: string } & Record<string, unknown>;
    return { type: String(type ?? 'unknown'), version: 1, props: rest };
  });
  const confidence = typeof flow.confidence === 'number' ? (flow.confidence <= 1 ? Math.round(flow.confidence * 100) : flow.confidence) : undefined;
  return {
    id: flowKey,
    text: String(flow.ai_message ?? flow.ai_response ?? ''),
    citations: Array.isArray(flow.data_sources_used) ? flow.data_sources_used.map(String) : [],
    components,
    chips: Array.isArray(flow.suggested_chips) ? flow.suggested_chips.map(String) : [],
    ...(flow.capability ? { capability: String(flow.capability) } : {}),
    ...(confidence !== undefined ? { confidence } : {}),
  };
}
