import { describe, it, expect } from 'vitest';
import { validateManifest } from './validate';
import type { PersonaManifest } from '../types';

const valid: PersonaManifest = {
  id: 'demo_persona',
  clientId: 'demo_client',
  marketId: 'financial-services',
  identity: { name: 'Maya J.', initials: 'MJ', role: 'Analyst', greeting: 'Maya' },
  capabilities: ['Proactive Intelligence', 'Automated Action'],
  flows: {
    chatFlows: { turn_1: { ai_message: 'hi' } },
    chipToFlowKey: { 'Show me': 'turn_1' },
    askTurnSequence: ['turn_1'],
    signalSequence: [],
  },
  signals: [{ id: 'SIG-1', title: 'A signal' }],
  dataSources: [{ id: 'ds-1', name: 'CRM' }],
  layout: 'split',
  ui: {
    greetingFlowKey: 'greeting',
    initialChips: ['Show me'],
    goldenPathChip: { greeting: 'Show me' },
    flowKeyToCapabilityTrigger: { greeting: 'home_load' },
    stats: [{ id: 'members', label: 'Active Members', value: '2,304' }],
    signalToChip: { 'SIG-1': 'Show me' },
    capabilityCallouts: [{ trigger: 'home_load' }],
  },
};

describe('validateManifest', () => {
  it('accepts a well-formed manifest', () => {
    expect(validateManifest(valid)).toEqual({ ok: true, errors: [] });
  });

  it('rejects a missing id', () => {
    const { id: _omit, ...bad } = valid;
    const res = validateManifest(bad);
    expect(res.ok).toBe(false);
    expect(res.errors.join()).toMatch(/id/);
  });

  it('rejects an unknown capability', () => {
    const res = validateManifest({ ...valid, capabilities: ['Telepathy'] });
    expect(res.ok).toBe(false);
    expect(res.errors.join()).toMatch(/capabilities/);
  });

  it('rejects an invalid layout', () => {
    const res = validateManifest({ ...valid, layout: 'sidebar' });
    expect(res.ok).toBe(false);
    expect(res.errors.join()).toMatch(/layout/);
  });

  it('rejects flows missing required sequences', () => {
    const res = validateManifest({ ...valid, flows: { chatFlows: {}, chipToFlowKey: {} } });
    expect(res.ok).toBe(false);
    expect(res.errors.join()).toMatch(/askTurnSequence|signalSequence/);
  });
});
