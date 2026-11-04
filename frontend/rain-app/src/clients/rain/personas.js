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

  // ── PRD v0.2 wave (doc/prd/RAIN_Platform_PRD_v0.2.docx §2) ────────────────
  // The v0.2 PRD's two MVP use cases: UC-01 smart scheduling with
  // pattern-based reminders, UC-02 rural population health insights.
  // Rosa Martínez (rural patient) is the patient-facing /patient route, not an
  // operator persona; Hannah Lee (payer / MCO analyst) is Phase 2 per the PRD.

  // 6 — Clinic scheduler / front desk (UC-01).
  rain_brooks: {
    id: 'rain_brooks',
    name: 'Kayla Brooks',
    initials: 'KB',
    role: 'Clinic Scheduler / Front Desk',
    greeting: 'Kayla',
    capabilities: [
      'Proactive Intelligence',
      'Converged Conversation',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 7 — Community health worker / care coordinator (UC-01, UC-02).
  rain_holloway: {
    id: 'rain_holloway',
    name: 'Denise Holloway',
    initials: 'DH',
    role: 'Community Health Worker / Care Coordinator',
    greeting: 'Denise',
    capabilities: [
      'Proactive Intelligence',
      'Friction Observability',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 8 — Provider: physician, NP, PA (UC-01, UC-02).
  rain_okafor: {
    id: 'rain_okafor',
    name: 'Dr. Samuel Okafor',
    initials: 'SO',
    role: 'Rural Provider (Physician, NP, PA)',
    greeting: 'Dr. Okafor',
    capabilities: [
      'Proactive Intelligence',
      'Converged Conversation',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 9 — Clinic medical / quality director (UC-02).
  rain_hargrove: {
    id: 'rain_hargrove',
    name: 'Dr. Linda Hargrove',
    initials: 'LH',
    role: 'Clinic Medical / Quality Director',
    greeting: 'Dr. Hargrove',
    capabilities: [
      'Proactive Intelligence',
      'Anomaly Detection',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 10 — State RHTP program manager (UC-02).
  rain_bell: {
    id: 'rain_bell',
    name: 'Marcus Bell',
    initials: 'MB',
    role: 'State RHTP Program Manager',
    greeting: 'Marcus',
    capabilities: [
      'Proactive Intelligence',
      'Anomaly Detection',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
  // 8 — Rural patient (UC-01): first-person briefing anchored to her own
  // synthetic record (backend persona "rosa"). English/Spanish, SMS-first.
  rain_martinez: {
    id: 'rain_martinez',
    name: 'Rosa Martínez',
    initials: 'RM',
    role: 'Rural Patient',
    greeting: 'Rosa',
    capabilities: [
      'Proactive Intelligence',
      'Converged Conversation',
      'Predictive Intelligence',
      'Automated Action',
    ],
  },
};
