import { describe, it, expect } from 'vitest';
import { getMarkets, findClient, getPersonaModule } from './registry';

// This standalone build registers one market (SLED) and one client (RAIN).
describe('registry (RAIN build)', () => {
  it('registers the SLED market with RAIN as its only client', () => {
    const markets = getMarkets();
    expect(markets.map((d) => d.id)).toEqual(['sled']);
    expect(markets[0].clients.map((c) => c.id)).toEqual(['rain']);
  });

  it('resolves RAIN from the SLED market', () => {
    const found = findClient('rain');
    expect(found?.market.id).toBe('sled');
    expect(found?.client.defaultPersonaId).toBe('rain_ceo');
  });

  it('finds every RAIN persona module', () => {
    for (const id of ['rain_ceo', 'rain_cmo', 'rain_cio', 'rain_state', 'rain_chw', 'rain_access']) {
      expect(getPersonaModule('rain', id)?.id).toBe(id);
    }
  });

  it('returns null for an unknown client', () => {
    expect(findClient('does_not_exist')).toBeNull();
  });
});
