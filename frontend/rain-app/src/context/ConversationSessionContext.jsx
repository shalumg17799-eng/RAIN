/**
 * ConversationSessionContext — a persona's chat thread, held above the router.
 *
 * The problem this exists for: the whole conversation — messages, chips, the
 * turn counter, the context panel — lives in `useManifestChat`, which lives in
 * `PersonaWorkspace`, which is the `/ask` route element. Any navigation unmounts
 * it and the thread is gone; coming back re-greets from turn zero.
 *
 * That is survivable for a persona whose answers stay on `/ask`. It is not
 * survivable for the Aramco HSE GM, because the man-down alert's own primary
 * action — "View Live Camera" — sends her to `/live-site`. Following the alert's
 * link destroyed the conversation the alert interrupted.
 *
 * So the thread is stashed here on the way out and handed back on the way in.
 *
 * **In-memory, deliberately.** A `useRef` map, not `sessionStorage`. It survives
 * every navigation inside the app, which is the whole requirement, and a browser
 * refresh still starts the demo clean — which is how a presenter resets between
 * run-throughs. Persisting across reloads would take that reset away and buy
 * nothing the acceptance path asks for.
 *
 * **Opt-in, per persona.** Only a manifest that sets `features.persistConversation`
 * passes a key, and `useManifestChat` ignores the store entirely without one. No
 * other tenant's behaviour changes.
 */
import { createContext, useCallback, useContext, useMemo, useRef } from 'react';

const ConversationSessionContext = createContext(null);

/**
 * Inert store, for the tree that has no provider (tests mounting a workspace on
 * its own). Saving into it is a no-op and loading always misses, so a consumer
 * behaves exactly as it did before this context existed.
 */
const DORMANT = {
  save: () => {},
  load: () => null,
  clear: () => {},
};

export function ConversationSessionProvider({ children }) {
  // A ref, not state: nothing renders off the stash, and writing it during an
  // unmount cleanup must not schedule a render on the way out.
  const store = useRef({});

  const save = useCallback((key, snapshot) => {
    if (!key) return;
    store.current[key] = snapshot;
  }, []);

  const load = useCallback((key) => (key ? store.current[key] ?? null : null), []);

  const clear = useCallback((key) => {
    if (!key) return;
    delete store.current[key];
  }, []);

  const value = useMemo(() => ({ save, load, clear }), [save, load, clear]);

  return (
    <ConversationSessionContext.Provider value={value}>
      {children}
    </ConversationSessionContext.Provider>
  );
}

/** Always returns a usable store — a no-op one outside the provider. */
export function useConversationSession() {
  return useContext(ConversationSessionContext) ?? DORMANT;
}

export default ConversationSessionContext;
