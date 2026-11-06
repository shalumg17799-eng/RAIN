/** Declarations split out of personaDemoSteps.js to keep it under 400 lines; behaviour unchanged. */


// ─── Risk & Fraud Executive (James R.) — 10 steps, 4 capabilities ─
export const riskSteps = [
  {
    label: 'Greeting — Proactive Intelligence',
    actions: [
      { type: 'navigate', path: '/' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Proactive Intelligence' },
    ],
  },
  {
    label: 'Turn 1 — Converged Conversation',
    actions: [
      { type: 'clickChip', partial: 'anomalies were detected' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Converged Conversation' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 2 — Anomaly Detection',
    actions: [
      { type: 'clickChip', partial: 'regulatory exposure' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Anomaly Detection' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 3 — Automated Action',
    actions: [
      { type: 'clickChip', partial: 'needs escalation' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Automated Action' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Confirm action — File SARs',
    actions: [
      { type: 'sleep', ms: 1000 },
      { type: 'confirmAction' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
    ],
  },
  {
    label: 'Journey — View member journey map',
    actions: [
      { type: 'navigate', path: '/journey' },
      { type: 'sleep', ms: 3500 },
    ],
  },
  {
    label: 'Risk — View risk dashboard',
    actions: [
      { type: 'navigate', path: '/risk' },
      { type: 'sleep', ms: 3500 },
    ],
  },
  {
    label: 'Data Sources — View connected integrations',
    actions: [
      { type: 'navigate', path: '/data-sources' },
      { type: 'sleep', ms: 4000 },
    ],
  },
  {
    label: 'Return to Ask the AI — Demo complete',
    actions: [
      { type: 'navigate', path: '/' },
      { type: 'sleep', ms: 2000 },
    ],
  },
];
