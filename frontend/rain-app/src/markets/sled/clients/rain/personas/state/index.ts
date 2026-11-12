import type { PersonaModule } from '@core/types';
import { personaUi } from '@/data/rain/personaUi';

export const rainStatePersona: PersonaModule = {
  id: 'rain_state',
  // Served by the backend (GET /api/v4/ui/data → personas.state), the same identity the manifest uses.
  identity: personaUi('state').identity,
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
