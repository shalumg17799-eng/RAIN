import { rainPersonas } from './personas';

/**
 * RAIN — Rural Health AI Infrastructure for Nevada (University of Nevada, Reno,
 * in partnership with Radiant Digital). A unified AI intelligence layer reasoning
 * across rural Nevada's fragmented clinical, telehealth, RPM, claims, transport,
 * public-health and SDOH systems. Five personas (added in delivery-priority order);
 * default is Dr. Maria Delgado-Reyes (Maternal Health). "Powered by Radiant Digital"
 * footer remains. Nav pages relabeled: Rural Health Intelligence + Care & Risk Signals.
 */
export default {
  id: 'rain',
  branding: {
    id: 'rain',
    name: 'University of Nevada, Reno',
    shortName: 'RAIN',
    nameLines: ['RAIN', 'Rural Health Intelligence'],
    tagline: 'University of Nevada, Reno',
    logo: '/logos/rain-logo.svg',
    favicon: '/logos/rain-logo.svg',
    // UNR "Nevada Blue" navy. In-chat visualizations use the standard navy base
    // theme; silver accents live in the logo/seal.
    primaryColor: '#003366',
    navLabels: { journey: 'Rural Health Intelligence', risk: 'Care & Risk Signals' },
  },
  auth: { username: 'rain', password: 'rain@9705' },
  personas: {
    defs: rainPersonas,
    // Dropdown order per spec: Delgado-Reyes, Whitehorse, Tomley, Nair, Yazzie.
    // Personas are added to this allowlist as each is completed (keeps the
    // dev-time validator green at every step).
    allowed: ['rain_delgado', 'rain_whitehorse', 'rain_tomley', 'rain_nair', 'rain_yazzie'],
    default: 'rain_delgado',
  },
};
