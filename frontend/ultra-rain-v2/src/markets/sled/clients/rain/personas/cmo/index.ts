import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainCmoPersona: PersonaModule = {
  id: 'rain_cmo',
  // Served by the backend (GET /api/v4/ui2/data → personas.cmo), the same identity the manifest uses.
  identity: personaUi('cmo').identity,
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
