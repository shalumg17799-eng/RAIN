/**
 * The fixed set of AI capabilities a persona can showcase. Personas reference
 * these by id; the capability-callout UI renders a diagram per capability.
 */
export const CAPABILITIES = [
  'Proactive Intelligence',
  'Converged Conversation',
  'Friction Observability',
  'Predictive Intelligence',
  'Anomaly Detection',
  'Automated Action',
] as const;

export type CapabilityId = (typeof CAPABILITIES)[number];
