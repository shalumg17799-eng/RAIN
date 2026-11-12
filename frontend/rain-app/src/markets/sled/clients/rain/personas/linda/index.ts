import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainLindaPersona: PersonaModule = {
  id: 'rain_linda',
  // Served by the backend (GET /api/v4/ui/data → personas.linda), the same identity the manifest uses.
  identity: personaUi('linda').identity,
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
