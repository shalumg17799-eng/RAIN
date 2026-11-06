/** Declarations split out of personaDemoSteps.js to keep it under 400 lines; behaviour unchanged. */


/**
 * Per-persona guided demo step definitions.
 * Each step has a label (shown in the overlay) and an actions array
 * that DemoRunner interprets sequentially.
 *
 * Action types:
 *   { type: 'navigate', path }
 *   { type: 'waitTyping' }
 *   { type: 'sleep', ms }
 *   { type: 'clickCapability', name }
 *   { type: 'clickChip', partial }
 *   { type: 'confirmAction' }
 *   { type: 'submitQuery', query, hint }
 *   { type: 'closeDrawer' }
 */

// ─── Operations & Analytics (Maya J.) — 14 steps, 6 capabilities ──
export const opsSteps = [
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
      { type: 'clickChip', partial: 'mortgage drop-off' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Converged Conversation' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 2 — Friction Observability',
    actions: [
      { type: 'clickChip', partial: 'show me who' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Friction Observability' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 3 — Predictive Intelligence',
    actions: [
      { type: 'clickChip', partial: 'Not yet' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Predictive Intelligence' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 4 — Anomaly Detection',
    actions: [
      { type: 'clickChip', partial: 'anomalies across systems' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Anomaly Detection' },
      { type: 'sleep', ms: 1500 },
    ],
  },
  {
    label: 'Turn 5 — Automated Action',
    actions: [
      { type: 'clickChip', partial: 'act on this' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Automated Action' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Confirm JIRA ticket & Slack notification',
    actions: [
      { type: 'sleep', ms: 1000 },
      { type: 'confirmAction' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 1500 },
      { type: 'clickChip', partial: 'notify them in Slack' },
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
    label: 'Journey — Ask about friction points',
    actions: [
      { type: 'submitQuery', query: "What's driving the mortgage drop-off?", hint: 'journey' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 3500 },
      { type: 'closeDrawer' },
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
    label: 'Risk — Analyze transaction anomalies',
    actions: [
      { type: 'clickChip', partial: 'transaction anomaly' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 3500 },
      { type: 'closeDrawer' },
    ],
  },
  {
    label: 'Risk — NCUA posture comparison',
    actions: [
      { type: 'clickChip', partial: 'NCUA posture' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 3500 },
      { type: 'closeDrawer' },
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

// ─── CX Operator (Priya K.) — 10 steps, 4 capabilities ──────────
export const cxSteps = [
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
      { type: 'clickChip', partial: 'members hitting friction' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Converged Conversation' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 2 — Friction Observability',
    actions: [
      { type: 'clickChip', partial: 'journeys underperform' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Friction Observability' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 3 — Automated Action',
    actions: [
      { type: 'clickChip', partial: 'intervention is needed' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Automated Action' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Confirm action — Proactive callback outreach',
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

// ─── Member Retention Analyst (Derek T.) — 10 steps, 4 capabilities ─
export const retentionSteps = [
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
      { type: 'clickChip', partial: 'churn signals' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Converged Conversation' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 2 — Predictive Intelligence',
    actions: [
      { type: 'clickChip', partial: 'segments are most at risk' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Predictive Intelligence' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Turn 3 — Automated Action',
    actions: [
      { type: 'clickChip', partial: 'Model the retention impact' },
      { type: 'waitTyping' },
      { type: 'sleep', ms: 2000 },
      { type: 'clickCapability', name: 'Automated Action' },
      { type: 'sleep', ms: 1000 },
    ],
  },
  {
    label: 'Confirm action — Generate retention brief',
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
