/**
 * Persona data-integrity validator (dev-time).
 *
 * The demo experience is wired by matching strings across three files per
 * persona — personaUIConfig (chips, stats, signals), personaFlowConfigs
 * (chipToFlowKey, sequences) and the chatFlows JSON. A single typo silently
 * dead-ends a flow at runtime (see the fallback cascade in useChatFlow.js).
 *
 * This module cross-checks those links for every (client × persona) pair and
 * reports breakages BEFORE you hit them in a demo. It runs automatically in dev
 * (wired from main.jsx) and can also be imported by a test.
 *
 * Severity:
 *   ERROR   → primary demo path is definitely broken (mapped to a non-existent
 *             flow, broken signal sequence, missing greeting/config).
 *   WARNING → link only resolves via the fuzzy keyword fallback, or a cosmetic
 *             hint points at a non-flow. Works today, brittle tomorrow.
 */

import { personas, CLIENT_PERSONAS } from '@/clients/registry';
import personaUIConfigs from '@/data/personaUIConfig';
import { getPersonaFlowConfigs } from '@/data/personaFlowConfigs';

// Chips the runtime treats specially (signal progression) — always resolvable.
const SIGNAL_PROGRESSION_CHIPS = new Set(['Next signal', 'Yes, walk me through them']);
// Recognized capability-trigger ids (home_load, ask_turn_1 … ask_turn_9).
const TRIGGER_RE = /^(home_load|ask_turn_\d+)$/;

/**
 * Mirror the *reliable* part of useChatFlow.handleChipClick: a chip resolves
 * deterministically if it's a signal-progression keyword, is mapped in
 * chipToFlowKey to a real flow (or __next_signal__), or exactly matches a
 * flow's user_query. Anything else only the fuzzy keyword fallback might catch.
 */
function chipResolves(chip, flowConfig) {
  if (SIGNAL_PROGRESSION_CHIPS.has(chip)) return true;
  const fk = flowConfig.chipToFlowKey?.[chip];
  if (fk === '__next_signal__') return true;
  if (fk && flowConfig.chatFlows[fk]) return true;
  const flows = flowConfig.chatFlows || {};
  return Object.keys(flows).some((k) => flows[k].user_query === chip);
}

export function validatePersonaData() {
  const errors = [];
  const warnings = [];

  for (const clientId of Object.keys(CLIENT_PERSONAS)) {
    const flowMap = getPersonaFlowConfigs(clientId);

    for (const personaId of CLIENT_PERSONAS[clientId]) {
      const ctx = `[${clientId} / ${personaId}]`;

      if (!personas[personaId]) {
        errors.push(`${ctx} no identity in persona registry`);
      }

      const flowConfig = flowMap[personaId];
      const ui = personaUIConfigs[personaId];

      if (!flowConfig) {
        errors.push(`${ctx} missing flow config (personaFlowConfigs)`);
        continue;
      }
      if (!ui) {
        warnings.push(`${ctx} missing UI config (personaUIConfig)`);
      }

      const flows = flowConfig.chatFlows || {};
      const hasFlow = (k) => Object.prototype.hasOwnProperty.call(flows, k);

      // ── Flow config integrity ──────────────────────────────────────────
      for (const [chip, fk] of Object.entries(flowConfig.chipToFlowKey || {})) {
        if (fk === '__next_signal__') continue;
        if (!hasFlow(fk)) {
          errors.push(`${ctx} chipToFlowKey["${chip}"] → "${fk}" — no such flow`);
        }
      }
      for (const fk of flowConfig.signalSequence || []) {
        if (!hasFlow(fk)) errors.push(`${ctx} signalSequence "${fk}" missing from chatFlows`);
      }
      for (const fk of flowConfig.askTurnSequence || []) {
        if (!hasFlow(fk)) warnings.push(`${ctx} askTurnSequence "${fk}" missing from chatFlows`);
      }
      if (flowConfig.actionTurnKey && !hasFlow(flowConfig.actionTurnKey)) {
        warnings.push(`${ctx} actionTurnKey "${flowConfig.actionTurnKey}" missing from chatFlows`);
      }

      if (!ui) continue;

      // ── UI config ↔ flow integrity ─────────────────────────────────────
      if (ui.greetingFlowKey && !hasFlow(ui.greetingFlowKey)) {
        errors.push(`${ctx} greetingFlowKey "${ui.greetingFlowKey}" missing from chatFlows`);
      }
      for (const [fk, chip] of Object.entries(ui.goldenPathChip || {})) {
        if (!hasFlow(fk)) warnings.push(`${ctx} goldenPathChip key "${fk}" is not a flow`);
        if (!chipResolves(chip, flowConfig)) {
          warnings.push(`${ctx} goldenPathChip["${fk}"] chip "${chip}" only resolves via fuzzy fallback`);
        }
      }
      for (const [fk, trig] of Object.entries(ui.flowKeyToCapabilityTrigger || {})) {
        if (!hasFlow(fk)) warnings.push(`${ctx} flowKeyToCapabilityTrigger key "${fk}" is not a flow`);
        if (!TRIGGER_RE.test(trig)) {
          warnings.push(`${ctx} flowKeyToCapabilityTrigger["${fk}"] → "${trig}" is not a recognized trigger`);
        }
      }
      for (const [sig, chip] of Object.entries(ui.signalToChip || {})) {
        if (!chipResolves(chip, flowConfig)) {
          warnings.push(`${ctx} signalToChip["${sig}"] chip "${chip}" only resolves via fuzzy fallback`);
        }
      }
      for (const chip of ui.initialChips || []) {
        if (!chipResolves(chip, flowConfig)) {
          warnings.push(`${ctx} initialChip "${chip}" only resolves via fuzzy fallback`);
        }
      }
      for (const s of ui.stats || []) {
        if (s.chipText && !chipResolves(s.chipText, flowConfig)) {
          warnings.push(`${ctx} stat "${s.id}" chipText "${s.chipText}" only resolves via fuzzy fallback`);
        }
      }
    }
  }

  return { errors, warnings };
}

/**
 * Run the validator and print a grouped console report. Never throws — a demo
 * should still load even if a flow is broken; the report tells you what to fix.
 * Returns the { errors, warnings } result so callers/tests can assert on it.
 */
export function reportPersonaData() {
  const { errors, warnings } = validatePersonaData();

  if (errors.length === 0 && warnings.length === 0) {
    // eslint-disable-next-line no-console
    console.info('%c✓ Persona data integrity: all flows wired correctly', 'color:#16a34a;font-weight:bold');
    return { errors, warnings };
  }

  const label = `Persona data integrity — ${errors.length} error(s), ${warnings.length} warning(s)`;
  // eslint-disable-next-line no-console
  console.groupCollapsed(`%c${label}`, `color:${errors.length ? '#dc2626' : '#d97706'};font-weight:bold`);
  // eslint-disable-next-line no-console
  errors.forEach((e) => console.error('ERROR  ' + e));
  // eslint-disable-next-line no-console
  warnings.forEach((w) => console.warn('WARN   ' + w));
  // eslint-disable-next-line no-console
  console.groupEnd();

  return { errors, warnings };
}
