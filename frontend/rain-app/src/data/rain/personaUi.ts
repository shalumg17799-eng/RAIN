/**
 * Each persona's identity, input placeholder, greeting subtitle and
 * notifications. Served by the backend (GET /api/v3/ui/data → section "personas").
 */
import type { PersonaIdentity, PersonaNotification } from '@core/types';
import type { PersonaKey } from './_shared/constants';
import { rainValue } from './_shared/backendData';

export interface RainPersonaUi {
  identity: PersonaIdentity;
  inputPlaceholder: string;
  greetingSubtitle: string;
  notifications: PersonaNotification[];
}

export const personaUi = (key: PersonaKey) => rainValue<RainPersonaUi>('personas', key);
