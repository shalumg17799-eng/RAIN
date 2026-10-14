export const tierFor = (score) => (score >= 85 ? 'high' : score >= 70 ? 'mid' : 'low');

export const colorFor = (tier) => ({
  high: '#16A34A',
  mid: '#D97706',
  low: '#DC2626',
}[tier]);

export const bgFor = (tier) => ({
  high: 'rgba(22, 163, 74, 0.10)',
  mid: 'rgba(217, 119, 6, 0.10)',
  low: 'rgba(220, 38, 38, 0.10)',
}[tier]);

export const borderFor = (tier) => ({
  high: 'rgba(22, 163, 74, 0.25)',
  mid: 'rgba(217, 119, 6, 0.25)',
  low: 'rgba(220, 38, 38, 0.30)',
}[tier]);

export const labelFor = (tier) => ({ high: 'High', mid: 'Moderate', low: 'Low' }[tier]);

export const auditStorageKey = 'rain.audit.v1';

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
