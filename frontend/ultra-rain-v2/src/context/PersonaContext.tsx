import { createContext, useContext, useState, useEffect, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useClient } from './ClientContext';
import { STORAGE_KEY } from '../config/clients';
import { getClientPersonas, getMarkets, findClient } from '@core/runtime/registry';
import { STORAGE_KEYS } from '@core/contract/storageKeys';
import type { PersonaIdentity, PersonaModule } from '@core/types';

declare global {
  interface Window {
    /** The active persona id, read by the guided-demo runner. */
    __activePersona?: string | null;
  }
}

/** The switcher's persona record (see `toPersona`). */
export interface Persona extends PersonaIdentity {
  id: string;
  illustrativePersona?: boolean;
}

export interface PersonaProviderProps {
  children?: ReactNode;
}

const PersonaContext = createContext<Persona | null>(null);
const PersonaListContext = createContext<Persona[]>([]);

const SESSION_KEY = STORAGE_KEYS.activePersona;

/**
 * The switcher's persona record: the registry's identity, flattened the way
 * the header and screens read it (`persona.name`, `persona.role`…).
 */
function toPersona(module: PersonaModule): Persona {
  return {
    id: module.id,
    ...module.identity,
    ...(module.illustrativePersona ? { illustrativePersona: true } : {}),
  };
}

/**
 * Which personas a client offers, in display order, and which one it opens
 * on — both read from the market registry, the one place a persona is
 * registered. (This used to be two hand-kept maps here, CLIENT_PERSONAS and
 * CLIENT_DEFAULT_PERSONA, that had to be kept in step with every client
 * manifest by a test.) A client the registry does not know falls back to the
 * first market's default client, which the picker can never produce.
 */
function personasFor(clientId: string | null): Persona[] {
  const modules = clientId ? getClientPersonas(clientId) : [];
  if (modules.length) return modules.map(toPersona);
  const market = getMarkets()[0];
  return getClientPersonas(market.defaultClientId).map(toPersona);
}

function defaultIdFor(clientId: string | null): string {
  const found = clientId ? findClient(clientId) : null;
  if (found) return found.client.defaultPersonaId;
  const market = getMarkets()[0];
  // A market's default client is always one of its own registered clients.
  return findClient(market.defaultClientId)!.client.defaultPersonaId;
}

function getClientIdFromStorage(): string | null {
  // Reads the same `selected_client` key ClientContext and BrandingContext use.
  // Needed because the initial persona is resolved in a useState initialiser,
  // where hooks are not available yet.
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function PersonaProvider({ children }: PersonaProviderProps) {
  const location = useLocation();
  const { clientId } = useClient();

  const allowedPersonas = useMemo(() => personasFor(clientId), [clientId]);
  const defaultId = useMemo(() => defaultIdFor(clientId), [clientId]);

  const [persona, setPersona] = useState<Persona>(() => {
    // Lazy init: read clientId directly from storage (hooks not available here)
    const cId = getClientIdFromStorage();
    const allowed = personasFor(cId);
    const byId = (id: string) => allowed.find((p) => p.id === id);

    const params = new URLSearchParams(window.location.search);
    const urlPersona = params.get('persona');
    if (urlPersona && byId(urlPersona)) return byId(urlPersona)!; // found just above
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored && byId(stored)) return byId(stored)!; // found just above
    return byId(defaultIdFor(cId)) || allowed[0];
  });

  // A persona the current client does not offer (the client just switched) gives
  // way to the client's default, in the same render.
  if (!allowedPersonas.some((p) => p.id === persona.id)) {
    setPersona(allowedPersonas.find((p) => p.id === defaultId) || allowedPersonas[0]);
  }

  // The persona switcher navigates with ?persona=; follow it when it changes.
  const [seenSearch, setSeenSearch] = useState(location.search);
  if (location.search !== seenSearch) {
    setSeenSearch(location.search);
    const urlPersona = new URLSearchParams(location.search).get('persona');
    const next = urlPersona && allowedPersonas.find((p) => p.id === urlPersona);
    if (next && urlPersona !== persona.id) setPersona(next);
  }

  // Remember the active persona for this tab (reloads come back to it).
  useEffect(() => {
    sessionStorage.setItem(SESSION_KEY, persona.id);
  }, [persona.id]);

  // Expose active persona id for DemoRunner
  useEffect(() => {
    window.__activePersona = persona.id;
    return () => { window.__activePersona = null; };
  }, [persona]);

  return (
    <PersonaContext.Provider value={persona}>
      <PersonaListContext.Provider value={allowedPersonas}>
        {children}
      </PersonaListContext.Provider>
    </PersonaContext.Provider>
  );
}

export function usePersona(): Persona {
  const ctx = useContext(PersonaContext);
  if (!ctx) throw new Error('usePersona must be used within PersonaProvider');
  return ctx;
}

export function usePersonaList(): Persona[] {
  return useContext(PersonaListContext);
}
