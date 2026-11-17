/**
 * Test harness: the provider stack a signed-in persona sees, for one client and
 * one persona, without a browser session.
 *
 * Mirrors App.tsx (SessionProvider → ClientProvider → ProtectedShell's stack)
 * and AppShell (Intraday → CriticalAlert → ConversationSession). The session is
 * seeded the same way a client-door sign-in seeds it: client scope in
 * sessionStorage, the client in localStorage, the persona as the active one.
 */
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { SessionProvider } from '@/context/SessionContext';
import { ClientProvider } from '@/context/ClientContext';
import { BrandingProvider } from '@/context/BrandingContext';
import { PersonaProvider } from '@/context/PersonaContext';
import { IntradayProvider } from '@/context/IntradayContext';
import { CriticalAlertProvider } from '@/context/CriticalAlertContext';
import { ConversationSessionProvider } from '@/context/ConversationSessionContext';
import { ThemeProvider } from '@core/providers/ThemeProvider';
import { STORAGE_KEYS } from '@core/contract/storageKeys';

/** Seed browser storage so the providers resolve `clientId` / `personaId`. */
export function seedSession(clientId: string, personaId?: string | null): void {
  sessionStorage.setItem(STORAGE_KEYS.session, clientId);
  localStorage.setItem(STORAGE_KEYS.selectedClient, clientId);
  if (personaId) sessionStorage.setItem(STORAGE_KEYS.activePersona, personaId);
}

export interface PersonaHarnessProps {
  clientId: string;
  personaId: string;
  path?: string;
  children?: ReactNode;
}

export function PersonaHarness({ clientId, personaId, path = '/ask', children }: PersonaHarnessProps) {
  seedSession(clientId, personaId);
  return (
    <MemoryRouter initialEntries={[`${path}?persona=${personaId}`]}>
      <SessionProvider>
        <ClientProvider>
          <BrandingProvider>
            <ThemeProvider>
              <PersonaProvider>
                <IntradayProvider>
                  <CriticalAlertProvider>
                    <ConversationSessionProvider>{children}</ConversationSessionProvider>
                  </CriticalAlertProvider>
                </IntradayProvider>
              </PersonaProvider>
            </ThemeProvider>
          </BrandingProvider>
        </ClientProvider>
      </SessionProvider>
    </MemoryRouter>
  );
}
