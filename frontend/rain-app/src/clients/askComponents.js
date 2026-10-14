/**
 * AskTheAI component-registry assembler.
 * ──────────────────────────────────────
 * Collects the RAIN inline component map (co-located in
 * src/clients/rain/askComponents.jsx) into the registries AskTheAI consumes.
 * This keeps client-specific component wiring out of the screen.
 *
 * ➜ To add a persona's inline visuals: edit src/clients/rain/askComponents.jsx.
 */

import { rainInlineComponents } from '@/clients/rain/askComponents';

// Right-panel component per (persona, turn number). RAIN personas compose their
// visuals inline in the chat thread, so there are no context panels.
export const contextPanelRegistries = {};

// flowKey → React elements for inline charts in the chat thread, per persona.
export const inlineComponentRegistries = {
  ...rainInlineComponents,
};
