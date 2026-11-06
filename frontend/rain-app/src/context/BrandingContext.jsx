import { createContext, useContext, useEffect } from 'react';
import { CLIENTS, DEFAULT_CLIENT_ID } from '../config/clients';
import { useClient } from './ClientContext';

/**
 * The active client's brand: name, mark, favicon, colour, nav labels.
 *
 * Derived from ClientContext rather than read from localStorage. It used to
 * read `selected_client` itself, which made it a *second* authority on which
 * tenant was open — and once sign-in became per-client that second reader was a
 * hole: a client-scoped session was correctly pinned by ClientContext while
 * BrandingProvider happily rendered whichever tenant the storage key named.
 *
 * One reader now. ClientContext resolves the session scope against the stored
 * pick; this turns that answer into a brand.
 *
 * `setClientId` is gone with the same change — nothing called it, and a setter
 * here would reintroduce exactly the second source of truth this removes.
 */

const BrandingContext = createContext(null);

export function BrandingProvider({ children }) {
  const { clientId: activeId } = useClient();

  // The fallback only matters if this ever renders outside the client guard;
  // ProtectedShell guarantees a client, so in practice `activeId` is set.
  const clientId = activeId && CLIENTS[activeId] ? activeId : DEFAULT_CLIENT_ID;
  const client = CLIENTS[clientId];

  // Update document title and favicon whenever client changes
  useEffect(() => {
    document.title = client.name;

    let link = document.querySelector("link[rel='icon']");
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }
    link.href = client.favicon;
  }, [client]);

  return (
    <BrandingContext.Provider value={{ client, clientId, CLIENTS }}>
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding() {
  return useContext(BrandingContext);
}
