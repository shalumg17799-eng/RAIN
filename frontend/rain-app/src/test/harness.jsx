/**
 * Test harness: the provider stack a signed-in persona sees, for one client and
 * one persona, without a browser session.
 *
 * Mirrors App.jsx (SessionProvider → ClientProvider → ProtectedShell's stack)
 * and AppShell (Intraday → CriticalAlert → ConversationSession). The session is
 * seeded the same way a client-door sign-in seeds it: client scope in
 * sessionStorage, the client in localStorage, the persona as the active one.
 */
import { MemoryRouter } from 'react-router-dom';
import { SessionProvider } from '@/context/SessionContext';
import { ClientProvider } from '@/context/ClientContext';
import { BrandingProvider } from '@/context/BrandingContext';
import { BrandProvider } from '@/context/BrandContext';
import { PersonaProvider } from '@/context/PersonaContext';
import { IntradayProvider } from '@/context/IntradayContext';
import { CriticalAlertProvider } from '@/context/CriticalAlertContext';
import { ConversationSessionProvider } from '@/context/ConversationSessionContext';
import { ThemeProvider } from '@core/providers/ThemeProvider';
import { STORAGE_KEYS } from '@core/contract/storageKeys';

/** Seed browser storage so the providers resolve `clientId` / `personaId`. */
export function seedSession(clientId, personaId) {
  sessionStorage.setItem(STORAGE_KEYS.session, clientId);
  localStorage.setItem(STORAGE_KEYS.selectedClient, clientId);
  if (personaId) sessionStorage.setItem(STORAGE_KEYS.activePersona, personaId);
}

export function PersonaHarness({ clientId, personaId, path = '/ask', children }) {
  seedSession(clientId, personaId);
  return (
    <MemoryRouter initialEntries={[`${path}?persona=${personaId}`]}>
      <SessionProvider>
        <ClientProvider>
          <BrandingProvider>
            <ThemeProvider>
              <PersonaProvider>
                <BrandProvider>
                  <IntradayProvider>
                    <CriticalAlertProvider>
                      <ConversationSessionProvider>{children}</ConversationSessionProvider>
                    </CriticalAlertProvider>
                  </IntradayProvider>
                </BrandProvider>
              </PersonaProvider>
            </ThemeProvider>
          </BrandingProvider>
        </ClientProvider>
      </SessionProvider>
    </MemoryRouter>
  );
}
