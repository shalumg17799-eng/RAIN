import { createContext, useContext, useState } from 'react';
import { CLIENTS, STORAGE_KEY } from '../config/clients';
import { useSession } from './SessionContext';

/**
 * Which client the app is currently showing.
 *
 * `selected_client` in localStorage is where the choice persists, but it is no
 * longer the *authority*. The session scope is:
 *
 *  • **Client scope** — you signed in at that client's own door. That client is
 *    the answer, and the stored value is ignored entirely. This is what stops a
 *    client-scoped session being moved to another tenant by editing localStorage
 *    in devtools, which worked until per-client credentials existed.
 *  • **Platform scope** — you signed in at `/login/ultra` and picked from the
 *    market picker, so the stored value behaves exactly as it always did.
 *
 * SessionProvider sits above this one, so `useSession()` is safe to read here.
 */

const ClientContext = createContext(null);

function readStoredClient() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved && CLIENTS[saved] ? saved : null;
  } catch {
    return null;
  }
}

export function ClientProvider({ children }) {
  const { scopedClientId, isUnlocked } = useSession();
  // Only a live session may resume a stored client. A locked visitor must reach
  // the picker, and before this gate a leftover `selected_client` carried them
  // straight past it into whichever tenant was open last — signing in at the
  // Ultra door dropped them into that client instead of the market picker,
  // because clearing the key does not clear this state. SessionProvider sits
  // above, so its scope is already resolved on this first render.
  const [picked, setPicked] = useState(() => (isUnlocked ? readStoredClient() : null));

  // A client-scoped session *is* its client. Nothing the picker or storage says
  // can override it, and it needs no separate state — deriving it here means
  // there is no second copy to fall out of sync on a sign-in.
  const clientId = scopedClientId && CLIENTS[scopedClientId] ? scopedClientId : picked;

  /** Enter the app as a client. Unknown ids are ignored rather than crashing. */
  function selectClient(id) {
    if (!CLIENTS[id]) return;
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch { /* private mode — the session still works, it just won't persist */ }
    setPicked(id);
  }

  /** Return to the client picker. No-op under client scope, which has no picker. */
  function clearClient() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch { /* nothing to clear */ }
    setPicked(null);
  }

  return (
    <ClientContext.Provider value={{ clientId, hasClient: !!clientId, selectClient, clearClient }}>
      {children}
    </ClientContext.Provider>
  );
}

export function useClient() {
  return useContext(ClientContext);
}
