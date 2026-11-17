import { STORAGE_KEYS } from '@core/contract/storageKeys';
// `loginSlug` is this client's front door: `/login/<slug>`, and the username on
// that page. It is mirrored in config/access.ts, which holds the matching
// password and is the module the gate actually reads — a test asserts the two
// agree, so neither can drift.
export const CLIENTS = {
  // ─── Commercial market — Newfold Digital (cross-brand SMB care) ──
  // ─── Oil & Gas market — Aramco (TrackLynk.AI HSE reference demo) ──
  // ─── Telecommunications market — AT&T (AI Billing Workbench) ────
  // ─── SLED market — Maryland DoIT ────────────────────────────────
  // ─── SLED market — AMISA ────────────────────────────────────────
  // ─── SLED market — Comptroller of Maryland ──────────────────────
  // ─── Healthcare market (proves the platform is multi-market) ────
  rain: {
    id: 'rain',
    loginSlug: 'rain',
    name: 'RAIN',
    shortName: 'RAIN',
    nameLines: ['RAIN', 'University of Nevada, Reno'],
    tagline: 'Value-Based Care Intelligence',
    logo: '/logos/rain-logo.svg',
    favicon: '/logos/rain-logo.svg',
    primaryColor: '#003366',
    navLabels: { ask: 'Ask AI' },
  },
};

/** Where a client lands after sign-in: its `homePath`, or the briefing. */
export const homePathFor = (clientId) => CLIENTS[clientId]?.homePath ?? '/ask';
export const STORAGE_KEY = STORAGE_KEYS.selectedClient;
