import { createContext, useContext, useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import {
  personas,
  CLIENT_PERSONAS,
  CLIENT_DEFAULT_PERSONA,
} from '@/clients/registry';

const PersonaContext = createContext(null);
const PersonaListContext = createContext([]);

const SESSION_KEY = 'active_persona';

// Persona allowlist and default are declared in the RAIN manifest
// (src/clients/rain/index.js) and aggregated by the registry.
const FALLBACK_CLIENT_ID = 'rain';

function getClientIdFromStorage() {
  try {
    const auth = JSON.parse(localStorage.getItem('auth_state') || 'null');
    return auth?.clientId || null;
  } catch {
    return null;
  }
}

function getAllowedIds(clientId) {
  return CLIENT_PERSONAS[clientId] || CLIENT_PERSONAS[FALLBACK_CLIENT_ID];
}

function getDefaultId(clientId) {
  return CLIENT_DEFAULT_PERSONA[clientId] || CLIENT_DEFAULT_PERSONA[FALLBACK_CLIENT_ID];
}

export function PersonaProvider({ children }) {
  const location = useLocation();
  const { auth } = useAuth();
  const clientId = auth?.clientId || null;

  const allowedIds = useMemo(() => getAllowedIds(clientId), [clientId]);
  const defaultId = useMemo(() => getDefaultId(clientId), [clientId]);

  const [persona, setPersona] = useState(() => {
    // Lazy init: read clientId directly from storage (hooks not available here)
    const cId = getClientIdFromStorage();
    const allowed = getAllowedIds(cId);
    const defId = getDefaultId(cId);

    const params = new URLSearchParams(window.location.search);
    const urlPersona = params.get('persona');
    if (urlPersona && personas[urlPersona] && allowed.includes(urlPersona)) {
      sessionStorage.setItem(SESSION_KEY, urlPersona);
      return personas[urlPersona];
    }
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored && personas[stored] && allowed.includes(stored)) {
      return personas[stored];
    }
    return personas[defId];
  });

  // When client switches, reset to client-default if current persona is not allowed
  useEffect(() => {
    if (!allowedIds.includes(persona.id)) {
      const next = personas[defaultId];
      sessionStorage.setItem(SESSION_KEY, next.id);
      setPersona(next);
    }
  }, [clientId]); // eslint-disable-line react-hooks/exhaustive-deps

  // React to URL ?persona= changes (persona switcher navigation)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlPersona = params.get('persona');
    if (
      urlPersona &&
      personas[urlPersona] &&
      allowedIds.includes(urlPersona) &&
      urlPersona !== persona.id
    ) {
      sessionStorage.setItem(SESSION_KEY, urlPersona);
      setPersona(personas[urlPersona]);
    }
  }, [location.search]); // eslint-disable-line react-hooks/exhaustive-deps

  const allowedPersonas = useMemo(
    () => allowedIds.map((id) => personas[id]).filter(Boolean),
    [allowedIds]
  );

  return (
    <PersonaContext.Provider value={persona}>
      <PersonaListContext.Provider value={allowedPersonas}>
        {children}
      </PersonaListContext.Provider>
    </PersonaContext.Provider>
  );
}

export function usePersona() {
  const ctx = useContext(PersonaContext);
  if (!ctx) throw new Error('usePersona must be used within PersonaProvider');
  return ctx;
}

export function usePersonaList() {
  return useContext(PersonaListContext);
}
