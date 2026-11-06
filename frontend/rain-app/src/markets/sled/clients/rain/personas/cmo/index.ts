import type { PersonaModule } from '@core/types';

export const rainCmoPersona: PersonaModule = {
  id: 'rain_cmo',
  // Keep identical to the manifest's identity: manifests.test.ts asserts it.
  identity: { name: 'Dr. Naomi Castellanos', initials: 'NC', role: 'Chief Medical Officer and Value-Based Care Quality Lead', greeting: 'Dr. Castellanos' },
  // A fictional persona on a role modelled on rural FQHC leadership (spec).
  illustrativePersona: true,
  load: () => import('./manifest'),
};
