/**
 * Each persona's identity, input placeholder, greeting subtitle and
 * notifications. Served by the backend (GET /api/v4/ui2/data → section "personas").
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

/** An operator's copy, or the patient's (`'patient'`: Linda Garcia, rain_patient). */
export const personaUi = (key: PersonaKey | 'patient') => rainValue<RainPersonaUi>('personas', key);
