import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainCeoPersona: PersonaModule = {
  id: 'rain_ceo',
  // Served by the backend (GET /api/v4/ui/data → personas.ceo), the same identity the manifest uses.
  identity: personaUi('ceo').identity,
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
