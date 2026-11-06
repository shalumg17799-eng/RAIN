import type { PersonaModule } from '@core/types';

export const rainAccessPersona: PersonaModule = {
  id: 'rain_access',
  // Keep identical to the manifest's identity: manifests.test.ts asserts it.
  identity: { name: 'Brandon Kee', initials: 'BK', role: 'Patient Access Coordinator', greeting: 'Brandon' },
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
