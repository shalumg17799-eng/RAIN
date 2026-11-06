/**
 * Client: RAIN, Rural Health AI Infrastructure for Nevada (University of
 * Nevada, Reno), the value-based care prototype v2. Shown through a fictional
 * FQHC network (Sierra Basin Community Health) at its Q3 contract checkpoint.
 *
 * Six operator personas in the spec's dropdown order, Gregory Haskins first
 * and default. Every one lands on Ask Cockpit.AI; the left navigation lists
 * only that persona's workbenches. The patient (Linda Garcia) is the /patient
 * view, not a switcher persona.
 *
 * Branding keeps v1's RAIN mark and the UNR wordmark in text (no UNR logo file
 * was supplied), on the spec's navy #003366 (12.6:1 on white). The theme
 * overrides the SLED market's Maryland blue and gold.
 *
 * Keep `branding` identical to this client's entry in src/config/clients.js:
 * BrandingContext and the sign-in pages read that map, and
 * `node scripts/check-registration.mjs rain` warns when the two drift.
 */
import type { ClientManifest } from '@core/types';
import { rainCeoPersona } from './personas/ceo';
import { rainCmoPersona } from './personas/cmo';
import { rainCioPersona } from './personas/cio';
import { rainStatePersona } from './personas/state';
import { rainChwPersona } from './personas/chw';
import { rainAccessPersona } from './personas/access';

export const rainClient: ClientManifest = {
  id: 'rain',
  marketId: 'sled',
  branding: {
    name: 'RAIN',
    shortName: 'RAIN',
    nameLines: ['RAIN', 'University of Nevada, Reno'],
    tagline: 'Value-Based Care Intelligence',
    logo: '/logos/rain-logo.svg',
    favicon: '/logos/rain-logo.svg',
    primaryColor: '#003366',
    navLabels: {
      ask: 'Ask AI',
    },
  },
  personas: [rainCeoPersona, rainCmoPersona, rainCioPersona, rainStatePersona, rainChwPersona, rainAccessPersona],
  defaultPersonaId: 'rain_ceo',
  theme: {
    light: {
      brand: '#003366',
      accent: '#0E7490',
      textMuted: '#4B5563',
      textSubtle: '#5B6472',
      chart: [
        '#003366', // 1 RAIN navy (brand)
        '#0E7490', // 2 teal
        '#7C3AED', // 3 violet
        '#4F6D8F', // 4 slate blue
        '#A16207', // 5 bronze
        '#94A3B8', // 6 cool grey
        '#BE185D', // 7 magenta
        '#1F2937', // 8 charcoal
      ],
    },
  },
};
