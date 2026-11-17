/**
 * Manifest validation. Runs at registry-build time and in tests so a
 * misconfigured tenant fails loudly and early instead of blank-rendering.
 *
 * Function-valued fields (contextPanel components, the answers factory)
 * can't be schema-checked meaningfully, so we validate the structural contract
 * and let those pass through.
 */

import { z } from 'zod';
import { CAPABILITIES } from '../types/capability';
import type { PersonaManifest } from '../types';
import { ICON_TONES, type IconTone } from '../contract/tone';

const identitySchema = z.object({
  name: z.string().min(1),
  initials: z.string().min(1),
  role: z.string().min(1),
  greeting: z.string().min(1),
});

const chatFlowConfigSchema = z.object({
  chatFlows: z.record(z.string(), z.looseObject({})),
  chipToFlowKey: z.record(z.string(), z.string()),
  askTurnSequence: z.array(z.string()),
  signalSequence: z.array(z.string()),
  actionTurnKey: z.string().optional(),
  actionConfirmMap: z.record(z.string(), z.looseObject({})).optional(),
});

export const personaManifestSchema = z.object({
  id: z.string().min(1),
  clientId: z.string().min(1),
  marketId: z.string().min(1),
  identity: identitySchema,
  capabilities: z.array(z.enum(CAPABILITIES)),
  flows: chatFlowConfigSchema,
  signals: z.array(z.looseObject({ id: z.string() })),
  dataSources: z.array(z.looseObject({ id: z.string() })),
  layout: z.enum(['split', 'inline', 'full']),
  ui: z.object({
    greetingFlowKey: z.string().min(1),
    initialChips: z.array(z.string()),
    goldenPathChip: z.record(z.string(), z.string()),
    flowKeyToCapabilityTrigger: z.record(z.string(), z.string()),
    // Tiles say what a figure is (`iconTone`), never how to colour it (rule 6).
    stats: z.array(z.looseObject({
      id: z.string(),
      iconTone: z.enum(ICON_TONES as [IconTone, ...IconTone[]]).optional(),
      iconColor: z.never().optional(),
      iconBg: z.never().optional(),
    })),
    signalToChip: z.record(z.string(), z.string()),
    capabilityCallouts: z.array(z.looseObject({})),
  }),
  features: z.looseObject({}).optional(),
  navLabels: z.record(z.string(), z.string()).optional(),
  // function-valued — presence only
  contextPanel: z.unknown().optional(),
  answers: z.unknown().optional(),
  catalog: z.array(z.looseObject({ type: z.string().regex(/^[a-z_]+\.[a-z0-9_]+$/), tier: z.literal(4), component: z.unknown() })).optional(),
});

export interface ValidationResult {
  ok: boolean;
  errors: string[];
}

/** Validate one persona manifest. Returns structured errors (never throws). */
export function validateManifest(manifest: unknown): ValidationResult {
  const result = personaManifestSchema.safeParse(manifest);
  if (result.success) return { ok: true, errors: [] };
  return {
    ok: false,
    errors: result.error.issues.map((i) => `${i.path.join('.') || '(root)'}: ${i.message}`),
  };
}

/** Throwing variant for registry-build time — fail fast on a bad tenant. */
export function assertManifest(manifest: unknown): PersonaManifest {
  const { ok, errors } = validateManifest(manifest);
  if (!ok) {
    const id =
      manifest && typeof manifest === 'object' && 'id' in manifest
        ? String((manifest as { id: unknown }).id)
        : '(unknown)';
    throw new Error(`Invalid PersonaManifest "${id}":\n  - ${errors.join('\n  - ')}`);
  }
  return manifest as PersonaManifest;
}
