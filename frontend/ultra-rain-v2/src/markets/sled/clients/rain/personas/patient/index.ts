import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainPatientPersona: PersonaModule = {
  id: 'rain_patient',
  // Served by the backend (GET /api/v4/ui2/data → personas.patient), the same identity the manifest uses.
  identity: personaUi('patient').identity,
  // A fictional patient (spec v2.1, Use Case C).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
