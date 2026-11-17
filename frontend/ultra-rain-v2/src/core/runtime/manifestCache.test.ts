/**
 * The race the browser walk found: factory personas build a new manifest on
 * every `load()`, and several shell parts load the active persona at once.
 * Concurrent loads must share one result, or each consumer holds a different
 * object and the workspace never becomes ready.
 */
import { describe, it, expect, vi } from 'vitest';
import { loadManifest, getCachedManifest } from './manifestCache';
import type { PersonaModule, PersonaManifest } from '../types';

function factoryModule(): PersonaModule & { calls: number } {
  const mod = {
    id: 'cx',
    identity: { name: 'Priya K.', initials: 'PK', role: 'CX', greeting: 'Priya' },
    calls: 0,
    load: vi.fn(async () => {
      mod.calls += 1;
      await new Promise((r) => setTimeout(r, 5));
      return { default: { id: 'cx', build: mod.calls } as unknown as PersonaManifest };
    }),
  };
  return mod;
}

describe('manifestCache', () => {
  it('shares one in-flight load between concurrent callers', async () => {
    const mod = factoryModule();
    const [a, b, c] = await Promise.all([loadManifest(mod), loadManifest(mod), loadManifest(mod)]);
    expect(mod.load).toHaveBeenCalledTimes(1);
    expect(a).toBe(b);
    expect(b).toBe(c);
    expect(getCachedManifest(mod)).toBe(a);
  });

  it('serves later callers from the cache', async () => {
    const mod = factoryModule();
    const first = await loadManifest(mod);
    const again = await loadManifest(mod);
    expect(again).toBe(first);
    expect(mod.load).toHaveBeenCalledTimes(1);
  });

  it('lets a failed load be retried', async () => {
    const mod = factoryModule();
    (mod.load as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('chunk failed'));
    await expect(loadManifest(mod)).rejects.toThrow('chunk failed');
    await expect(loadManifest(mod)).resolves.toBeTruthy();
  });
});
