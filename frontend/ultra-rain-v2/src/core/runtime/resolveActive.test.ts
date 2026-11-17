import { describe, it, expect, vi } from 'vitest';
import type { PersonaModule } from '../types';

// Mock the market registry so resolution is deterministic and independent of
// which tenants have been migrated.
const persona = (id: string): PersonaModule => ({
  id,
  identity: { name: id, initials: 'XX', role: 'r', greeting: 'g' },
  load: async () => ({ default: {} as never }),
});

vi.mock('@markets', () => ({
  marketRegistry: [
    {
      id: 'financial-services',
      name: 'Financial Services',
      defaultClientId: 'acme',
      clients: [
        {
          id: 'acme',
          marketId: 'financial-services',
          branding: {} as never,
          defaultPersonaId: 'ops',
          personas: [persona('ops'), persona('cx')],
        },
      ],
    },
  ],
}));

const { resolveActive } = await import('./resolveActive');

describe('resolveActive', () => {
  it('returns null for an unknown/unmigrated client', () => {
    expect(resolveActive('penfed', 'ops')).toBeNull();
  });

  it('returns null when no client id is given', () => {
    expect(resolveActive(null)).toBeNull();
  });

  it('resolves a requested persona that the client exposes', () => {
    const r = resolveActive('acme', 'cx');
    expect(r?.persona.id).toBe('cx');
    expect(r?.client.id).toBe('acme');
    expect(r?.market.id).toBe('financial-services');
  });

  it('returns null for a requested-but-unregistered persona (defers to legacy)', () => {
    expect(resolveActive('acme', 'not_a_persona')).toBeNull();
  });

  it('falls back to the client default when no persona requested', () => {
    expect(resolveActive('acme')?.persona.id).toBe('ops');
  });
});
