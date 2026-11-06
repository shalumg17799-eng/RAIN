import type { PersonaModule } from '@core/types';

export const rainCeoPersona: PersonaModule = {
  id: 'rain_ceo',
  // Keep identical to the manifest's identity: manifests.test.ts asserts it.
  identity: { name: 'Gregory Haskins, MBA', initials: 'GH', role: 'Chief Executive Officer', greeting: 'Gregory' },
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
