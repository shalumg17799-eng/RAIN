/**
 * The persona switcher reads the market registry: for every client it lists
 * exactly the registered personas in order, opens on the client's default,
 * honours a valid `?persona=`, and ignores one the client does not offer.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useEffect } from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SessionProvider } from './SessionContext';
import { ClientProvider } from './ClientContext';
import { PersonaProvider, usePersona, usePersonaList } from './PersonaContext';
import { getMarkets } from '@core/runtime/registry';
import { STORAGE_KEYS } from '@core/contract/storageKeys';

const clients = getMarkets().flatMap((m) => m.clients);
const seen = { persona: null, list: [] };

function Probe() {
  const persona = usePersona();
  const list = usePersonaList();
  useEffect(() => { seen.persona = persona; seen.list = list; });
  return null;
}

function mount(clientId, search = '') {
  sessionStorage.setItem(STORAGE_KEYS.session, clientId);
  localStorage.setItem(STORAGE_KEYS.selectedClient, clientId);
  window.history.replaceState({}, '', `/ask${search}`);
  render(
    <MemoryRouter initialEntries={[`/ask${search}`]}>
      <SessionProvider><ClientProvider><PersonaProvider><Probe /></PersonaProvider></ClientProvider></SessionProvider>
    </MemoryRouter>,
  );
}

describe('PersonaContext reads the registry', () => {
  beforeEach(() => { sessionStorage.clear(); localStorage.clear(); });

  it.each(clients.map((c) => [c.id, c]))('%s: lists its registered personas and opens on its default', (_id, client) => {
    mount(client.id);
    expect(seen.list.map((p) => p.id)).toEqual(client.personas.map((p) => p.id));
    expect(seen.persona.id).toBe(client.defaultPersonaId);
    const module = client.personas.find((p) => p.id === client.defaultPersonaId);
    expect(seen.persona).toMatchObject({ name: module.identity.name, role: module.identity.role, initials: module.identity.initials });
  });

  it('selects a persona the client offers from the URL, and ignores one it does not', () => {
    mount('rain', '?persona=rain_cmo');
    expect(seen.persona.id).toBe('rain_cmo');
    sessionStorage.clear();
    mount('rain', '?persona=not_a_rain_persona');
    expect(seen.persona.id).toBe('rain_ceo');
  });
});
