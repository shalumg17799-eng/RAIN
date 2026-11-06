/**
 * Registry integrity — every registered persona actually loads and validates.
 *
 * `validateManifest` existed but nothing in production or in CI ever called it,
 * so a persona could be registered in `src/markets` with a malformed manifest,
 * a missing ui field, or an invented capability name and the only symptom would
 * be a blank screen at demo time.
 *
 * The identity checks matter because a persona's identity is written in two
 * places (the PersonaModule the switcher reads and the PersonaManifest the
 * workspace reads); a mismatch shows the wrong name in the switcher versus the
 * greeting. (The legacy data/personas record and PersonaContext's hand-kept
 * CLIENT_PERSONAS map are gone: the switcher now reads the registry.)
 */
import { describe, it, expect } from 'vitest';
import { getMarkets } from './registry';
import { validateManifest } from './validate';
import { ICONS } from '../contract/icons';
import type { PersonaManifest } from '../types';

const markets = getMarkets();

const entries = markets.flatMap((market) =>
  market.clients.flatMap((client) =>
    client.personas.map((persona) => ({ market, client, persona })),
  ),
);

describe('market registry integrity', () => {
  it('registers exactly the one market this build serves', () => {
    expect(markets.map((m) => m.id)).toEqual(['sled']);
  });

  it('gives every market tile a registered icon and a hex gradient', () => {
    for (const market of markets) {
      if (!market.tile) continue;
      expect(ICONS[market.tile.icon], `${market.id} tile icon "${market.tile.icon}" is not in core/contract/icons`).toBeDefined();
      for (const c of [market.tile.from, market.tile.to]) expect(c, `${market.id} tile colour`).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it('gives every market a default client that exists in it', () => {
    for (const market of markets) {
      expect(market.clients.length, `${market.id} has no clients`).toBeGreaterThan(0);
      expect(
        market.clients.some((c) => c.id === market.defaultClientId),
        `${market.id} defaultClientId "${market.defaultClientId}" is not one of its clients`,
      ).toBe(true);
    }
  });

  it('gives every client a default persona that exists in it', () => {
    for (const market of markets) {
      for (const client of market.clients) {
        expect(
          client.personas.some((p) => p.id === client.defaultPersonaId),
          `${client.id} defaultPersonaId "${client.defaultPersonaId}" is not one of its personas`,
        ).toBe(true);
      }
    }
  });

  it('keeps client ids unique across markets (findClient returns the first match)', () => {
    const ids = markets.flatMap((m) => m.clients.map((c) => c.id));
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('keeps persona ids unique within each client', () => {
    // Not unique globally by design: the shared factory personas (ops, cx,
    // retention, risk) are registered under several financial-services clients.
    for (const market of markets) {
      for (const client of market.clients) {
        const ids = client.personas.map((p) => p.id);
        expect(new Set(ids).size, `${client.id} registers a duplicate persona id`).toBe(ids.length);
      }
    }
  });
});

/**
 * Content drift that predates these checks. Each entry is a real (cosmetic) bug
 * in an existing tenant, left in place rather than silently edited as a side
 * effect of unrelated work. The allowlist exists so the checks below can stay
 * strict for everything else — nothing new may be added to it.
 *
 *  • risk — goldenPathChip['risk_greeting'] reads "What anomalies were
 *    detected?" but the turn offers "What anomalies were detected overnight?",
 *    so no chip is highlighted on that persona's greeting.
 *  • penfed_capmarkets — flowKeyToCapabilityTrigger maps turn_6_actions to
 *    'ask_turn_6', which does not exist in the shared capabilityCallouts.json
 *    (home_load, ask_turn_1..5), so that turn renders no capability badge.
 */
const KNOWN_DRIFT = {
  goldenPathChip: new Set(['risk']),
  capabilityTrigger: new Set(['penfed_capmarkets']),
};

describe('persona manifests', () => {
  it.each(entries.map((e) => [e.persona.id, e] as const))(
    '%s loads and satisfies the PersonaManifest schema',
    async (_id, entry) => {
      const mod = await entry.persona.load();
      const manifest = mod.default as PersonaManifest;

      const { ok, errors } = validateManifest(manifest);
      expect(ok, `${entry.persona.id}:\n  - ${errors.join('\n  - ')}`).toBe(true);

      // The manifest must agree with where it is registered.
      expect(manifest.id).toBe(entry.persona.id);
      expect(manifest.clientId).toBe(entry.client.id);
      expect(manifest.marketId).toBe(entry.market.id);

      // Identity is duplicated in the module; it must not drift.
      expect(manifest.identity).toEqual(entry.persona.identity);

      // The greeting flow has to exist, or the persona opens on an empty thread.
      expect(
        Object.keys(manifest.flows.chatFlows),
        `${entry.persona.id} greetingFlowKey "${manifest.ui.greetingFlowKey}" is not a defined flow`,
      ).toContain(manifest.ui.greetingFlowKey);

      // Every chip the golden path recommends must be offered by that turn, or
      // the "recommended" highlight points at a chip that is never rendered.
      if (!KNOWN_DRIFT.goldenPathChip.has(entry.persona.id)) {
        for (const [flowKey, chip] of Object.entries(manifest.ui.goldenPathChip)) {
          const flow = manifest.flows.chatFlows[flowKey] as { suggested_chips?: string[] } | undefined;
          if (!flow?.suggested_chips) continue;
          expect(
            flow.suggested_chips,
            `${entry.persona.id}: goldenPathChip["${flowKey}"] = "${chip}" is not among that turn's suggested_chips`,
          ).toContain(chip);
        }
      }

      // Every capability trigger must resolve to a callout, or the capability
      // tag renders as a dead button.
      if (!KNOWN_DRIFT.capabilityTrigger.has(entry.persona.id)) {
        const triggers = new Set(manifest.ui.capabilityCallouts.map((c) => c.trigger));
        for (const trigger of Object.values(manifest.ui.flowKeyToCapabilityTrigger)) {
          expect(
            triggers,
            `${entry.persona.id}: capability trigger "${trigger}" has no matching callout`,
          ).toContain(trigger);
        }
      }
    },
    // Loading a manifest pulls in that persona's whole component graph. The
    // heaviest (nfcu_platform_admin: mermaid + neo4j-nvl) can exceed the 5s
    // default when the suite runs alongside typecheck/build on a busy machine.
    20_000,
  );

});
