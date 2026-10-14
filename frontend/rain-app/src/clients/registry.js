/**
 * Client Registry
 * ────────────────
 * Single source of truth for the RAIN client. The client lives in
 * src/clients/rain/ with an index.js manifest declaring its branding, login
 * credential, and personas. This file turns that manifest into the lookup maps
 * the rest of the app consumes.
 */

import rain from './rain';

const MANIFESTS = [rain];

// ─── Branding ────────────────────────────────────────────────────────────────
// CLIENTS[clientId] → branding object (name, logo, colors, navLabels, isParent…)
export const CLIENTS = Object.fromEntries(
  MANIFESTS.map((m) => [m.id, m.branding])
);

export const DEFAULT_CLIENT_ID = 'rain';
export const STORAGE_KEY = 'selected_client';

// ─── Auth ────────────────────────────────────────────────────────────────────
// CREDENTIALS[username] → { password, clientId }
export const CREDENTIALS = Object.fromEntries(
  MANIFESTS.map((m) => [
    m.auth.username,
    { password: m.auth.password, clientId: m.id },
  ])
);

// ─── Personas ────────────────────────────────────────────────────────────────
// Flat registry of every persona definition, keyed by persona id.
export const personas = MANIFESTS.reduce(
  (acc, m) => Object.assign(acc, m.personas.defs),
  {}
);

// CLIENT_PERSONAS[clientId] → allowed persona id allowlist
export const CLIENT_PERSONAS = Object.fromEntries(
  MANIFESTS.map((m) => [m.id, m.personas.allowed])
);

// CLIENT_DEFAULT_PERSONA[clientId] → default persona id
export const CLIENT_DEFAULT_PERSONA = Object.fromEntries(
  MANIFESTS.map((m) => [m.id, m.personas.default])
);
