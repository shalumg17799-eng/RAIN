import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainAccessPersona: PersonaModule = {
  id: 'rain_access',
  // Served by the backend (GET /api/v4/ui2/data → personas.access), the same identity the manifest uses.
  identity: personaUi('access').identity,
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
