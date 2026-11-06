import { createContext, useContext, useState } from 'react';
import {
  ADMIN_ACCESS_KEY,
  verifyLogin,
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
 *   'ultra'      signed in at the platform door. Gets the market picker and can
 *                enter any client through it.
 *   '<clientId>' signed in at one client's own door. Is that client. No picker,
 *                and no route to a different tenant.
 *   null         locked.
 *
 * The scope is deliberately authoritative over `selected_client` in
 * localStorage. That key used to be the only record of which tenant you were
 * in, which meant editing it in devtools switched tenant — fine when one
 * credential opened everything, not fine now that a client is handed a link
 * that is supposed to open exactly their own. ClientContext reconciles against
 * this value; see the note there.
 *
 * Scope is per browser TAB (sessionStorage), for both the credential path and
 * the `?access=` bypass. A refresh keeps you in — which matters mid-demo — but
 * closing the tab does not leave the machine unlocked.
 *
 * ⚠️  Not a security boundary. See config/access.ts.
 */

const SESSION_KEY = STORAGE_KEYS.session;
const ULTRA_SCOPE = 'ultra';

const SessionContext = createContext(null);

/** Drop the selected client so an unlock always lands on the picker. */
function clearStoredClient() {
  try {
    localStorage.removeItem(CLIENT_KEY);
  } catch { /* private mode — nothing to clear */ }
}

function writeScope(scope) {
  try {
    sessionStorage.setItem(SESSION_KEY, scope);
  } catch { /* the session still holds in memory */ }
}

/** Remove `access` from the address bar, keeping every other param and the hash. */
function stripAccessParam(params) {
  params.delete('access');
  const query = params.toString();
  const url = window.location.pathname + (query ? `?${query}` : '') + window.location.hash;
  window.history.replaceState({}, '', url);
}

/**
 * Consume `?access=…` if present: grant platform scope for the tab, then strip
 * the token from the URL while preserving every other query param AND the hash.
 *
 * Runs in a useState initialiser rather than an effect so the very first render
 * is already unlocked — no flash of the login screen. It is idempotent, which
 * matters because StrictMode invokes it twice in development.
 */
function readInitialScope() {
  // A client's direct link — `/login/<slug>?access=…` — comes first and wins
  // over whatever this tab held before, because a link that names a client
  // should open that client. ClientGateRoute then sees the matching scope and
  // forwards to /ask, so the sign-in form never shows.
  try {
    const params = new URLSearchParams(window.location.search);
    const clientId = clientIdForAccessLink(window.location.pathname, params.get('access'));
    if (clientId) {
      stripAccessParam(params);
      writeScope(clientId);
      try {
        localStorage.setItem(CLIENT_KEY, clientId);
      } catch { /* private mode — the scope still carries the client */ }
      return clientId;
    }
  } catch { /* fall through to the stored scope */ }

  try {
    const stored = sessionStorage.getItem(SESSION_KEY);
    // 'true' is the pre-scope format. Reading it as platform scope means a tab
    // that was open across the deploy stays signed in rather than being thrown
    // out mid-demo.
    if (stored === 'true') return ULTRA_SCOPE;
    if (stored) return stored;
  } catch { /* storage unavailable — fall through to the URL check */ }

  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get('access') !== ADMIN_ACCESS_KEY) return null;

    stripAccessParam(params);
    writeScope(ULTRA_SCOPE);

    // The admin key means "take me to the markets", so never resume a client
    // left over from a previous visit. This runs before ClientProvider reads
    // that key, because SessionProvider sits above it.
    clearStoredClient();
    return ULTRA_SCOPE;
  } catch {
    return null;
  }
}

export function SessionProvider({ children }) {
  const [scope, setScope] = useState(readInitialScope);
  // The door the next locked render should show, when a sign-out knows which
  // one that is. Null — a fresh tab, or a sign-out from the picker — means the
  // platform door.
  //
  // This exists because a sign-out cannot simply navigate itself. React Router
  // runs navigation in a transition, so the urgent `setScope(null)` commits
  // first, at the OLD location: `ProtectedShell` re-renders unlocked, redirects
  // to its own destination, and that redirect supersedes the pending one. The
  // guard therefore has to be *told* where to go rather than raced. It used to
  // reach the right page by accident, back when the guard's fallback was the
  // last tenant this browser had been in.
  //
  // Deliberately state, not storage: it lives exactly as long as the tab's
  // current page, so reopening the app is unaffected by it.
  const [exitPath, setExitPath] = useState(null);

  /** Platform door. Returns false on a bad credential so the form can show an error. */
  function signInAsUltra(username, password) {
    if (!verifyLogin(username, password)) return false;
    writeScope(ULTRA_SCOPE);
    clearStoredClient();
    setExitPath(null);
    setScope(ULTRA_SCOPE);
    return true;
  }

  /**
   * A client's own door. Scoped to that client, so the credential handed to
   * NFCU cannot be typed into Aramco's page — `verifyClientLogin` checks
   * against one client, not against all of them.
   */
  function signInAsClient(clientId, username, password) {
    if (!verifyClientLogin(clientId, username, password)) return false;
    writeScope(clientId);
    try {
      localStorage.setItem(CLIENT_KEY, clientId);
    } catch { /* private mode — the scope still carries the client */ }
    setExitPath(null);
    setScope(clientId);
    return true;
  }

  /**
   * Full sign out — the scope and the selected client both go.
   *
   * `destination` is the door to land on — the `/login/<slug>` of the client
   * being left, however that client was entered. The guard reads it; see
   * `exitPath` above for why the caller cannot just navigate.
   */
  function signOut(destination) {
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
        isPlatformScope: scope === ULTRA_SCOPE,
        /** The client this session is locked to, or null under platform scope. */
        scopedClientId: scope && scope !== ULTRA_SCOPE ? scope : null,
        /** Where a locked render should send you, or null for the platform door. */
        exitPath,
        signInAsUltra,
        signInAsClient,
        signOut,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
