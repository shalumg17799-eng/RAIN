import type { PersonaModule } from '@core/types';

export const rainCioPersona: PersonaModule = {
  id: 'rain_cio',
  // Keep identical to the manifest's identity: manifests.test.ts asserts it.
  identity: { name: 'Raj Malhotra', initials: 'RM', role: 'Chief Information Officer and Data and AI Governance Lead', greeting: 'Raj' },
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
