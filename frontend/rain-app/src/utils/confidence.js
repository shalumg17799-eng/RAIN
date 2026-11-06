import { STORAGE_KEYS } from '@core/contract/storageKeys';
export const tierFor = (score) => (score >= 85 ? 'high' : score >= 70 ? 'mid' : 'low');

// Confidence tiers read from theme tokens so they adapt to light/dark and any brand.
export const colorFor = (tier) => ({
  high: 'var(--color-conf-high)',
  mid: 'var(--color-conf-med)',
  low: 'var(--color-conf-low)',
}[tier]);

export const bgFor = (tier) => ({
  high: 'color-mix(in srgb, var(--color-conf-high) 12%, transparent)',
  mid: 'color-mix(in srgb, var(--color-conf-med) 12%, transparent)',
  low: 'color-mix(in srgb, var(--color-conf-low) 12%, transparent)',
}[tier]);

export const borderFor = (tier) => ({
  high: 'color-mix(in srgb, var(--color-conf-high) 28%, transparent)',
  mid: 'color-mix(in srgb, var(--color-conf-med) 28%, transparent)',
  low: 'color-mix(in srgb, var(--color-conf-low) 30%, transparent)',
}[tier]);

export const labelFor = (tier) => ({ high: 'High', mid: 'Moderate', low: 'Low' }[tier]);

export const auditStorageKey = STORAGE_KEYS.confidenceAudit;

export function persistEscalation(entry) {
  try {
    const raw = sessionStorage.getItem(auditStorageKey);
    const list = raw ? JSON.parse(raw) : [];
    if (list.some((e) => e.auditId === entry.auditId)) return;
    list.unshift(entry);
    sessionStorage.setItem(auditStorageKey, JSON.stringify(list.slice(0, 50)));
  } catch {
    /* sessionStorage unavailable — silently no-op */
  }
}

export function loadAuditTrail() {
  try {
    const raw = sessionStorage.getItem(auditStorageKey);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}
