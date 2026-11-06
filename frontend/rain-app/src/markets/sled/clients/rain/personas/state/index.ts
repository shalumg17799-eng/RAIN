import type { PersonaModule } from '@core/types';

export const rainStatePersona: PersonaModule = {
  id: 'rain_state',
  // Keep identical to the manifest's identity: manifests.test.ts asserts it.
  identity: { name: 'Dr. Lauren Pike', initials: 'LP', role: 'Program Lead, Rural Health Outcomes Accelerator', greeting: 'Dr. Pike' },
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
