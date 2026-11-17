/**
 * Demo access configuration — SINGLE SOURCE OF TRUTH for the gate in front of
 * the app.
 *
 * ⚠️  THIS IS NOT A SECURITY BOUNDARY, AND IT IS NOT AUTHENTICATION. This is a
 * scripted demo prototype with no backend. The credential below ships in the
 * client bundle, so anyone who can load the page can read it. It stops a URL
 * being casually shared and opening straight into the demo; it stops nothing
 * else. It does NOT keep any data away from anyone — all of it is in the same
 * bundle. Do NOT model real authentication on this file, and do not treat the
 * `rain` credential as a login the backend should honour.
 *
 * When this app grows a real backend, this module is the one place to swap for
 * a real identity provider.
 *
 * This build serves one tenant through one door, `/login/rain`. The
 * multi-tenant platform it was cut from also had a platform door and a market
 * picker; neither exists here.
 */

/** The only tenant this build serves. */
export const RAIN_CLIENT_ID = 'rain';

/**
 * URL query token (`?access=…`) that skips sign-in on any route.
 * Overridable at build time so the key can be changed without editing source.
 */
export const ADMIN_ACCESS_KEY = import.meta.env.VITE_POC_ACCESS_KEY || 'rdvr@9705';

export interface ClientCredential {
  /** URL segment: `/login/<slug>`. Also the username. */
  slug: string;
  password: string;
}

/**
 * The credential, keyed by the client id in `config/clients.js`.
 *
 * The slug is declared here rather than derived from the client id or short
 * name. It becomes a public URL someone will paste into an email, so it must
 * not change silently when a display name is edited.
 *
 * `access.test.ts` asserts this map covers every registered client, so adding a
 * client without a credential fails the suite instead of shipping a tenant
 * whose front door 404s.
 */
export const CLIENT_CREDENTIALS: Record<string, ClientCredential> = {
  rain: { slug: 'rain', password: 'rain@9705' },
};

/**
 * Validate a credential against ONE client: case-insensitive username,
 * case-sensitive password, fails closed on anything that is not a string.
 */
export function verifyClientLogin(
  clientId: string,
  username: string,
  password: string,
): boolean {
  if (typeof username !== 'string' || typeof password !== 'string') return false;
  const cred = CLIENT_CREDENTIALS[clientId];
  if (!cred) return false;
  return username.toLowerCase().trim() === cred.slug && password === cred.password;
}

/** `/login/<slug>` → client id, or null for nonsense. */
export function clientIdForSlug(slug: string): string | null {
  if (typeof slug !== 'string') return null;
  const wanted = slug.toLowerCase().trim();
  const found = Object.entries(CLIENT_CREDENTIALS).find(([, c]) => c.slug === wanted);
  return found ? found[0] : null;
}

/**
 * Direct link into the client: `/login/<slug>?access=<token>` skips the sign-in
 * form and lands on the briefing. The token is the client's own password
 * (`/login/rain?access=rain@9705`).
 *
 * Returns the client id to scope the session to, or null when the path is not a
 * client door or the token does not open it.
 */
export function clientIdForAccessLink(pathname: string, token: string | null): string | null {
  if (typeof pathname !== 'string' || typeof token !== 'string' || !token) return null;
  const match = /^\/login\/([^/]+)\/?$/.exec(pathname);
  if (!match) return null;
  const clientId = clientIdForSlug(decodeURIComponent(match[1]));
  if (!clientId) return null;
  if (token === CLIENT_CREDENTIALS[clientId].password) {
    return clientId;
  }
  return null;
}

/**
 * The shareable direct link for a client — the one `clientIdForAccessLink`
 * accepts — on the given origin. Null if the client has no gate.
 */
export function directAccessUrl(clientId: string, origin: string): string | null {
  const cred = CLIENT_CREDENTIALS[clientId];
  if (!cred) return null;
  return `${origin}/login/${cred.slug}/?access=${cred.password}`;
}

/** Client id → its `/login/<slug>` segment, or null if the client has no gate. */
export function slugForClientId(clientId: string): string | null {
  return CLIENT_CREDENTIALS[clientId]?.slug ?? null;
}

/** The sign-in path for a client, falling back to the one door this build has. */
export function loginPathForClientId(clientId: string | null | undefined): string {
  const slug = clientId ? slugForClientId(clientId) : null;
  return `/login/${slug || CLIENT_CREDENTIALS[RAIN_CLIENT_ID].slug}`;
}

/** The single sign-in door. Every redirect in the app resolves here. */
export const LOGIN_PATH = loginPathForClientId(RAIN_CLIENT_ID);
