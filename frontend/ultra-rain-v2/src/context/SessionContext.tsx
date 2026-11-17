import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import {
  ADMIN_ACCESS_KEY,
  RAIN_CLIENT_ID,
  verifyClientLogin,
  clientIdForAccessLink,
} from '../config/access';
import { STORAGE_KEY as CLIENT_KEY } from '../config/clients';
import { STORAGE_KEYS } from '@core/contract/storageKeys';

/**
 * The gate — whether this tab has been let in, and *as what*.
 *
 * The session carries a **scope**, not a boolean:
 *
 *   '<clientId>' signed in at the client's own door. Is that client.
 *   null         locked.
 *
 * This build serves exactly one tenant, so the only non-null scope is its id.
 * The scope is still modelled as a client id rather than a boolean because it
 * is what ClientContext resolves against, and because it is deliberately
 * authoritative over `selected_client` in localStorage — editing that key in
 * devtools must not be able to move a session to a different tenant.
 *
 * Scope is per browser TAB (sessionStorage), for both the credential path and
 * the `?access=` bypass. A refresh keeps you in — which matters mid-demo — but
 * closing the tab does not leave the machine unlocked.
 *
 * ⚠️  Not a security boundary, and not authentication. See config/access.ts.
 */

const SESSION_KEY = STORAGE_KEYS.session;

/** What `useSession()` returns. */
export interface SessionValue {
  /** The client id, or null when locked. */
  scope: string | null;
  isUnlocked: boolean;
  /** The client this session is locked to, or null when locked. */
  scopedClientId: string | null;
  /** Where a locked render should send you, or null for the default door. */
  exitPath: string | null;
  signInAsClient: (clientId: string, username: string, password: string) => boolean;
  signOut: (destination?: string | null) => void;
}

export interface SessionProviderProps {
  children?: ReactNode;
}

const SessionContext = createContext<SessionValue | null>(null);

/** Drop the selected client so an unlock always re-resolves it. */
function clearStoredClient() {
  try {
    localStorage.removeItem(CLIENT_KEY);
  } catch { /* private mode — nothing to clear */ }
}

function writeScope(scope: string): void {
  try {
    sessionStorage.setItem(SESSION_KEY, scope);
  } catch { /* the session still holds in memory */ }
}

function rememberClient(clientId: string): void {
  try {
    localStorage.setItem(CLIENT_KEY, clientId);
  } catch { /* private mode — the scope still carries the client */ }
}

/** Remove `access` from the address bar, keeping every other param and the hash. */
function stripAccessParam(params: URLSearchParams): void {
  params.delete('access');
  const query = params.toString();
  const url = window.location.pathname + (query ? `?${query}` : '') + window.location.hash;
  window.history.replaceState({}, '', url);
}

/**
 * Consume `?access=…` if present: grant scope for the tab, then strip the token
 * from the URL while preserving every other query param AND the hash.
 *
 * Runs in a useState initialiser rather than an effect so the very first render
 * is already unlocked — no flash of the login screen. It is idempotent, which
 * matters because StrictMode invokes it twice in development.
 */
function readInitialScope(): string | null {
  // The client's direct link — `/login/<slug>?access=<password>` — comes first
  // and wins over whatever this tab held before. ClientGateRoute then sees the
  // matching scope and forwards to /ask, so the sign-in form never shows.
  try {
    const params = new URLSearchParams(window.location.search);
    const clientId = clientIdForAccessLink(window.location.pathname, params.get('access'));
    if (clientId) {
      stripAccessParam(params);
      writeScope(clientId);
      rememberClient(clientId);
      return clientId;
    }
  } catch { /* fall through to the stored scope */ }

  try {
    const stored = sessionStorage.getItem(SESSION_KEY);
    // 'true' and 'ultra' are the multi-tenant platform's formats. Mapping them
    // onto the one tenant this build has means a tab that was open across the
    // switch stays signed in rather than being thrown out mid-demo.
    if (stored === 'true' || stored === 'ultra') return RAIN_CLIENT_ID;
    if (stored) return stored;
  } catch { /* storage unavailable — fall through to the URL check */ }

  // The access token (`?access=rdvr@9705`) skips the form on any route.
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get('access') !== ADMIN_ACCESS_KEY) return null;

    stripAccessParam(params);
    writeScope(RAIN_CLIENT_ID);
    rememberClient(RAIN_CLIENT_ID);
    return RAIN_CLIENT_ID;
  } catch {
    return null;
  }
}

export function SessionProvider({ children }: SessionProviderProps) {
  const [scope, setScope] = useState<string | null>(readInitialScope);
  // The door the next locked render should show, when a sign-out knows which
  // one that is. Null means the default door.
  //
  // This exists because a sign-out cannot simply navigate itself. React Router
  // runs navigation in a transition, so the urgent `setScope(null)` commits
  // first, at the OLD location: `ProtectedShell` re-renders unlocked, redirects
  // to its own destination, and that redirect supersedes the pending one. The
  // guard therefore has to be *told* where to go rather than raced.
  //
  // Deliberately state, not storage: it lives exactly as long as the tab's
  // current page, so reopening the app is unaffected by it.
  const [exitPath, setExitPath] = useState<string | null>(null);

  /**
   * The client's door. Scoped to that client — `verifyClientLogin` checks
   * against one client, not against all of them.
   *
   * Returns false on a bad credential so the form can show an error.
   */
  function signInAsClient(clientId: string, username: string, password: string): boolean {
    if (!verifyClientLogin(clientId, username, password)) return false;
    writeScope(clientId);
    rememberClient(clientId);
    setExitPath(null);
    setScope(clientId);
    return true;
  }

  /**
   * Full sign out — the scope and the selected client both go.
   *
   * `destination` is the door to land on (`/login/<slug>`). The guard reads
   * it; see `exitPath` above for why the caller cannot just navigate.
   */
  function signOut(destination?: string | null): void {
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch { /* nothing to clear */ }
    clearStoredClient();
    setExitPath(destination || null);
    setScope(null);
  }

  return (
    <SessionContext.Provider
      value={{
        scope,
        isUnlocked: scope !== null,
        /** The client this session is locked to, or null when locked. */
        scopedClientId: scope || null,
        /** Where a locked render should send you, or null for the default door. */
        exitPath,
        signInAsClient,
        signOut,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  // SessionProvider wraps the whole app (App.tsx), so every consumer is inside it.
  return useContext(SessionContext)!;
}
