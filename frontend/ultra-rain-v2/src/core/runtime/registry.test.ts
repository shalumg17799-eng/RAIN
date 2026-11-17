import { describe, it, expect } from 'vitest';
import { getMarkets, findClient, getPersonaModule } from './registry';

describe('registry', () => {
  it('registers the SLED market', () => {
    const ids = getMarkets().map((d) => d.id);
    expect(ids).toEqual(['sled']);
  });

  it('resolves the client from its market', () => {
    const found = findClient('rain');
    expect(found?.market.id).toBe('sled');
    expect(found?.client.defaultPersonaId).toBe('rain_ceo');
  });

  it('finds a persona module', () => {
    expect(getPersonaModule('rain', 'rain_chw')?.id).toBe('rain_chw');
    expect(getPersonaModule('rain', 'nope')).toBeFalsy();
  });

  it('returns null for an unknown client', () => {
    expect(findClient('does_not_exist')).toBeNull();
  });
});
