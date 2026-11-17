/**
 * The six capability tags for RAIN's Use Case A conversations: the callout each
 * tag opens, and the copy for each capability's architecture deep-dive. Served
 * by the backend (GET /api/v4/ui2/data → section "capabilities").
 */
import { rainValue } from './backendData';

export const CAPABILITY_CALLOUTS = rainValue<Array<{ trigger: string; capabilityName: string; eyebrow: string; description: string }>>('capabilities', 'CAPABILITY_CALLOUTS');

export const CAPABILITY_DIAGRAMS = rainValue<Record<string, Record<string, unknown>>>('capabilities', 'CAPABILITY_DIAGRAMS');
