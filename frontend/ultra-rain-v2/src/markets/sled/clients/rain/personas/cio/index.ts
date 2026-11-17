import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainCioPersona: PersonaModule = {
  id: 'rain_cio',
  // Served by the backend (GET /api/v4/ui2/data → personas.cio), the same identity the manifest uses.
  identity: personaUi('cio').identity,
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
