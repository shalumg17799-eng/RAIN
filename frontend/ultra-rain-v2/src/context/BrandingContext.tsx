import { createContext, useContext, useEffect } from 'react';
import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { CLIENTS } from '../config/clients';
import { LOGIN_PATH } from '../config/access';
import { useClient } from './ClientContext';
import type { ClientConfig } from './ClientContext';

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

/** What `useBranding()` returns. */
export interface BrandingValue {
  client: ClientConfig;
  clientId: string;
  CLIENTS: Record<string, ClientConfig | undefined>;
}

export interface BrandingProviderProps {
  children?: ReactNode;
}

/** `CLIENTS`, read by any id (an unknown one is undefined). */
const CLIENTS_BY_ID: Record<string, ClientConfig | undefined> = CLIENTS;

const BrandingContext = createContext<BrandingValue | null>(null);

export function BrandingProvider({ children }: BrandingProviderProps) {
  const { clientId: activeId } = useClient();

  // ProtectedShell mounts this only once a client is resolved, so `activeId` is
  // set. There is no default tenant to fall back to: without a known client the
  // app returns to the sign-in door.
  const clientId = activeId && CLIENTS_BY_ID[activeId] ? activeId : null;
  const client = clientId ? CLIENTS_BY_ID[clientId] : null;

  // Update document title and favicon whenever client changes
  useEffect(() => {
    if (!client) return;
    document.title = client.name;

    let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
    if (!link) {
      link = document.createElement('link');
      link.rel = 'icon';
      document.head.appendChild(link);
    }
    link.href = client.favicon;
  }, [client]);

  if (!client || !clientId) return <Navigate to={LOGIN_PATH} replace />;

  return (
    <BrandingContext.Provider value={{ client, clientId, CLIENTS: CLIENTS_BY_ID }}>
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding(): BrandingValue {
  // BrandingProvider wraps the signed-in shell (App.tsx's ProtectedShell).
  return useContext(BrandingContext)!;
}
