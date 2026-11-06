/**
 * Every list a persona renders by id has unique ids. A duplicate is a React
 * key collision (one card can stand in for another on update) and an ambiguous
 * record for the API — the browser walk found two Comptroller data sources
 * sharing `ds-mdc-11`.
 */
import { describe, it, expect } from 'vitest';
import { getMarkets } from './registry';
import type { PersonaManifest } from '../types';

const entries = getMarkets().flatMap((m) => m.clients.flatMap((c) => c.personas.map((p) => ({ c, p }))));
const dupes = (ids: unknown[]) => ids.filter((id, i) => ids.indexOf(id) !== i);

describe('persona lists have unique ids', () => {
  it.each(entries.map((e) => [`${e.c.id}/${e.p.id}`, e] as const))('%s', async (_l, { p }) => {
    const m = (await p.load()).default as PersonaManifest;
    expect(dupes(m.dataSources.map((d) => d.id)), 'dataSources').toEqual([]);
    expect(dupes(m.signals.map((s) => s.id)), 'signals').toEqual([]);
    expect(dupes(m.ui.stats.map((s) => s.id)), 'ui.stats').toEqual([]);
  }, 20_000);
});
