import type { PersonaModule } from '@core/types';

export const rainChwPersona: PersonaModule = {
  id: 'rain_chw',
  // Keep identical to the manifest's identity: manifests.test.ts asserts it.
  identity: { name: 'Teresa Lopez, CHW', initials: 'TL', role: 'Community Health Worker and Care Coordinator', greeting: 'Teresa' },
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
