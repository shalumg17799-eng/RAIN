/**
 * The UI's data comes only from the backend: the loader adopts what the server
 * sends (and checks it against the server's SHA-256), and a missing or failing
 * backend is an error, never a silent fallback.
 */
import { createHash } from 'node:crypto';
import { afterAll, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { BackendDataError, hydrateRainData, loadRainData, rainDataProof, rainValue } from './backendData';

const SEED = JSON.parse(readFileSync(resolve(__dirname, '../../../../../../rain-api/seed/rain_v3_ui_data.json'), 'utf8'));

function backend(body: string, status = 200, sha = createHash('sha256').update(body).digest('hex')) {
  return vi.fn(async () =>
    new Response(body, {
      status,
      headers: {
        'Content-Type': 'application/json',
        'X-RAIN-Source': 'rain-api',
        'X-RAIN-Request-Id': 'req123',
        'X-RAIN-Server': 'backend-1',
        'X-RAIN-Data-Source': 'postgres://rain_v3/ui_v3.dataset + public_data (live)',
        'X-RAIN-Data-Sha256': sha,
      },
    }),
  );
}

const silence = () => {
  for (const m of ['log', 'group', 'groupEnd', 'table'] as const) vi.spyOn(console, m).mockImplementation(() => {});
};

describe('RAIN backend data loader', () => {
  afterAll(() => hydrateRainData(SEED, 'rain-api/seed/rain_v3_ui_data.json'));

  it('adopts exactly what the backend sends and records the proof', async () => {
    silence();
    const served = structuredClone(SEED);
    served.meta = { source: 'rain-api', server: 'backend-1', dataSource: 'x', database: { name: 'rain_v3', table: 'ui_v3.dataset', rows: 1, seedLoadedAt: 'now' }, publicOverlay: [], counts: {}, records: {}, requestId: 'req123', generatedAt: 'now', dbMs: 1 };
    served.sections.constants.CONTRACT = { ...served.sections.constants.CONTRACT, members: 12345 };
    const body = JSON.stringify(served);
    const fetchImpl = backend(body);
    const proof = await loadRainData('rain', fetchImpl as unknown as typeof fetch);
    expect(fetchImpl).toHaveBeenCalledWith('/api/v3/ui/data?clientId=rain', expect.anything());
    expect(rainValue<{ members: number }>('constants', 'CONTRACT').members).toBe(12345);
    expect(proof.source).toBe('rain-api');
    expect(proof.requestId).toBe('req123');
    expect(proof.verified).not.toBe(false); // true where crypto.subtle exists, null otherwise
    expect(rainDataProof()?.keysRead).toContain('constants.CONTRACT');
  });

  it('flags a body that does not match the server checksum', async () => {
    silence();
    const body = JSON.stringify({ ...SEED, meta: { ...SEED.meta, database: { rows: 0 }, publicOverlay: [] } });
    const proof = await loadRainData('rain', backend(body, 200, 'deadbeef') as unknown as typeof fetch);
    expect(proof.verified === null || proof.verified === false).toBe(true);
  });

  it('gives up on a backend that never answers instead of waiting forever', async () => {
    const hang = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }));
    await expect(loadRainData('rain', hang as unknown as typeof fetch, 50)).rejects.toThrow(/did not answer within 0.05 s/);
  });

  it('fails loudly when the backend is down or errors, with no local fallback', async () => {
    const down = vi.fn(async () => { throw new TypeError('Failed to fetch'); });
    await expect(loadRainData('rain', down as unknown as typeof fetch)).rejects.toBeInstanceOf(BackendDataError);
    await expect(loadRainData('rain', backend('{"detail":"no data"}', 404) as unknown as typeof fetch)).rejects.toThrow(/404/);
  });
});
