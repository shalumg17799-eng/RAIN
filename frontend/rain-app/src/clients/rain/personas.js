/**
 * RAIN — Rural Health AI Infrastructure for Nevada (University of Nevada, Reno).
 * Five rural Nevada health operations personas, each tied to a cross-system
 * intelligence use case. All five thread through a single root-cause event — the
 * Battle Mountain Critical Access Hospital labor & delivery closure (March 1, 2026).
 * Built in delivery-priority order; personas are added to the manifest allowlist
 * as each is completed. Default is Dr. Maria Delgado-Reyes (Maternal Health).
 */

export const rainPersonas = {
  // 1 — Maternal Health (default). Nav page: Rural Health Intelligence.
  rain_delgado: {
    id: 'rain_delgado',
    name: 'Dr. Maria Delgado-Reyes',
    initials: 'MD',
    role: 'Rural Health Medical Director & Chief Medical Officer',
    greeting: 'Dr. Delgado-Reyes',
    capabilities: [
      'Proactive Intelligence',
      'Anomaly Detection',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 2 — Chronic Disease Management. Nav page: Ask the AI.
  rain_whitehorse: {
    id: 'rain_whitehorse',
    name: 'Sarah Whitehorse, RN',
    initials: 'SW',
    role: 'Care Coordination Lead, Chronic Disease Management',
    greeting: 'Sarah',
    capabilities: [
      'Proactive Intelligence',
      'Converged Conversation',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 3 — Operational Visibility (mobile-app frame). Nav page: Care & Risk Signals.
  rain_tomley: {
    id: 'rain_tomley',
    name: 'James Tomley',
    initials: 'JT',
    role: 'Rural Clinic & Critical Access Hospital Operations Lead',
    greeting: 'James',
    capabilities: [
      'Proactive Intelligence',
      'Friction Observability',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 4 — Population Health & Equity. Nav page: Rural Health Intelligence.
  rain_nair: {
    id: 'rain_nair',
    name: 'Dr. Priya Nair',
    initials: 'PN',
    role: 'Director, Rural Population Health & Access Equity',
    greeting: 'Dr. Nair',
    capabilities: [
      'Proactive Intelligence',
      'Converged Conversation',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 5 — Interoperability & Data Quality. Nav page: Data Sources.
  rain_yazzie: {
    id: 'rain_yazzie',
    name: 'David Yazzie',
    initials: 'DY',
    role: 'Director, Health Data Engineering & Interoperability',
    greeting: 'David',
    capabilities: [
      'Proactive Intelligence',
      'Anomaly Detection',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
};
