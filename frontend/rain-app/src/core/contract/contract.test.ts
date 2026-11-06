/**
 * The shared vocabularies: every legacy value in today's fixtures maps onto the
 * standard, and every legacy signal reads into the strict signal schema.
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { toStatus, toConfidence, STATUSES } from './status';
import { normalizeSignal, signalSchema } from './signal';
import { resolveIcon, iconIdOf, ICONS } from './icons';
import { EVENTS, deckEvent, emitEvent, onEvent } from './events';
import { STORAGE_KEYS } from './storageKeys';

const DATA = join(__dirname, '../../data');
function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (n.endsWith('.json')) out.push(p);
  }
  return out;
}

describe('status vocabulary', () => {
  it('passes the five standard values through', () => {
    for (const s of STATUSES) expect(toStatus(s)).toBe(s);
  });

  it.each([
    ['ok', 'good'], ['Healthy', 'good'], ['online', 'good'], ['pass', 'good'], ['compliant', 'good'], ['G', 'good'],
    ['amber', 'warning'], ['at_risk', 'warning'], ['Under Review', 'warning'], ['watch', 'warning'],
    ['red', 'critical'], ['breached', 'critical'], ['disconnected', 'critical'], ['alarm', 'critical'],
    ['in progress', 'info'], ['scheduled', 'info'],
    ['unknown', 'neutral'], ['not_started', 'neutral'],
  ])('maps %s → %s', (legacy, std) => {
    expect(toStatus(legacy)).toBe(std);
  });

  it('reads a number as a health score and anything else as neutral', () => {
    expect(toStatus(92)).toBe('good');
    expect(toStatus(70)).toBe('warning');
    expect(toStatus(12)).toBe('critical');
    expect(toStatus(undefined)).toBe('neutral');
    expect(toStatus('something new')).toBe('neutral');
  });

  it('reads every confidence spelling as 0–100', () => {
    expect(toConfidence(0.92)?.score).toBe(92);
    expect(toConfidence(87)?.score).toBe(87);
    expect(toConfidence('94%')?.score).toBe(94);
    expect(toConfidence({ score: 0.8, label: 'High' })).toEqual({ score: 80, label: 'High', rationale: undefined });
    expect(toConfidence(null)).toBeNull();
  });
});

describe('signal contract', () => {
  const files = walk(DATA).filter((f) => /signals?\.json$/i.test(f));
  const records = files.flatMap((f) => {
    const j = JSON.parse(readFileSync(f, 'utf8'));
    const arr = Array.isArray(j) ? j : j.signals ?? [];
    return (arr as unknown[]).filter((s): s is Record<string, unknown> => !!s && typeof s === 'object' && 'id' in s && 'title' in s)
      .map((s) => [f.replace(DATA, 'data'), s] as const);
  });

  it('reads every legacy signal into the strict schema', () => {
    const failures = records
      .map(([file, raw]) => ({ file, id: raw.id, result: signalSchema.safeParse(normalizeSignal(raw)) }))
      .filter((r) => !r.result.success)
      .map((r) => `${r.file} ${String(r.id)}: ${r.result.success ? '' : r.result.error.issues[0].message}`);
    expect(failures).toEqual([]);
  });

  it('keeps the meaning of a legacy record', () => {
    const s = normalizeSignal({
      id: 'S1', title: 'Queue spike', severity: 'critical', type: 'queue', affected_count: 42,
      sources: ['Genesys'], metric_text: '18 min', confidence: { score: 0.91 },
    });
    expect(s).toEqual({
      id: 'S1', title: 'Queue spike', status: 'critical', category: 'queue', affectedCount: 42,
      sources: ['Genesys'], metricText: '18 min', confidence: { score: 91, label: undefined, rationale: undefined },
    });
  });
});

describe('icon registry', () => {
  it('resolves ids and passes components through', () => {
    expect(resolveIcon('users')).toBe(ICONS.users);
    expect(resolveIcon(ICONS.gauge)).toBe(ICONS.gauge);
    expect(resolveIcon('no-such-icon')).toBeUndefined();
    expect(iconIdOf(ICONS['alert-triangle'])).toBe('alert-triangle');
  });
});

describe('event and storage registries', () => {
  it('keeps the strings tenants already ship', () => {
    expect(EVENTS.ussfcuCeoOpenPresentation).toBe('ussfcu-ceo:open-presentation');
    expect(deckEvent('esfcu-ceo-deck', 'open-chat')).toBe('esfcu-ceo-deck:open-chat');
    expect(STORAGE_KEYS.selectedClient).toBe('selected_client');
    expect(new Set(Object.values(EVENTS)).size).toBe(Object.values(EVENTS).length);
    expect(new Set(Object.values(STORAGE_KEYS)).size).toBe(Object.values(STORAGE_KEYS).length);
  });

  it('delivers an event detail to a listener and unsubscribes', () => {
    const seen: unknown[] = [];
    const off = onEvent<{ text: string }>(EVENTS.sclacAsk, (d) => seen.push(d.text));
    emitEvent(EVENTS.sclacAsk, { text: 'hello' });
    off();
    emitEvent(EVENTS.sclacAsk, { text: 'ignored' });
    expect(seen).toEqual(['hello']);
  });
});
