import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainChwPersona: PersonaModule = {
  id: 'rain_chw',
  // Served by the backend (GET /api/v3/ui/data → personas.chw), the same identity the manifest uses.
  identity: personaUi('chw').identity,
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
