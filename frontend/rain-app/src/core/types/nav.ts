/**
 * Sidebar nav slots. A persona lists the ones it shows (`features.navSlots`)
 * and may relabel them; a page guards itself by its slot (`usePageAccess`).
 */

export type NavKey =
  | 'ask'
  | 'journey'
  | 'risk'
  | 'governance'
  | 'agentObservability'
  | 'agentInventory'
  // Oil & Gas / HSE slots. Additive: no existing persona lists them in
  // `features.navSlots`, and they are absent from the default slot set, so
  // every other market's sidebar is unchanged.
  | 'liveSite'
  | 'permits'
  | 'muster'
  // Telecom / AI Billing Workbench slots. Additive in the same way: absent from
  // the default slot set and from every other persona's `features.navSlots`.
  | 'patterns'
  | 'dashboard'
  | 'history'
  | 'adminConsole'
  // ESFCU risk/fraud slot. Additive in the same way: absent from the default
  // slot set and listed only by the persona that owns the page.
  | 'fraudOperations'
  // SLED / VOCE. Where a saved report actually lives — added because both DoIT
  // personas offered a "save to my reports" chip with no destination behind it.
  // Additive: absent from the default slot set and listed only by those two.
  | 'myReports'
  // USSFCU Finance (Fiona). The spec's two navigation pages. Additive: absent
  // from the default slot set and listed only by the Finance persona.
  | 'portfolioRisk'
  | 'scenarios'
  // SLED / Comptroller of Maryland. The v2 spec's stage pages (Plan,
  // Package, Approve, Publish, Measure). Additive: absent from the default
  // slot set and listed only by the Comptroller's comms persona.
  | 'audiencePlan'
  | 'packageReview'
  | 'approvalBoard'
  | 'channelSchedule'
  | 'results'
  // SLED / Comptroller of Maryland v3 (one warehouse, three decision-makers):
  // Rhea's executive view, Faye's fraud workspace, data health and lineage,
  // and cases, and the architecture page (/data-foundation, because
  // /architecture is SCLAC's). Additive: absent from the default slot set and
  // listed only by the Comptroller's personas.
  | 'execView'
  | 'fraudWorkspace'
  | 'warehouseHealth'
  | 'caseFiles'
  | 'dataFoundation'
  // SLED / Superior Court of Los Angeles County (Insights Factory). The spec's
  // scorecard, feedback-loop and architecture pages. Additive: absent from the
  // default slot set and listed only by the SCLAC personas.
  | 'scorecard'
  | 'feedbackLoop'
  | 'architecture'
  // SCLAC "Ask the KPI" (Oct 18 requirements): the KRI panel, the six division
  // spaces and the 36-courthouse comparison. Additive in the same way.
  | 'kriPanel'
  | 'divisionSpaces'
  | 'courthouseComparison'
  // SCLAC Strategy and Transformation KPI Tracker (Oct 21 demo spec): Jeff's
  // one-screen tracker. Additive: absent from the default slot set and listed
  // only by Jeff.
  | 'transformation'
  // SCLAC's CX program view (the Court Experience Index). Additive in the same
  // way: absent from the default slot set and listed only by the SCLAC personas.
  | 'cxProgram'
  // Telecom / Lyte Corporate Intelligence. One page per leader (churn,
  // competition, expansion) and two shared ones: acquisition onboarding on the
  // data foundation (/onboarding, because /data-foundation is the
  // Comptroller's) and the Azure architecture (/platform, because
  // /architecture is SCLAC's). Additive: absent from the default slot set and
  // listed only by the Lyte personas.
  | 'churnRetention'
  | 'competitiveDynamics'
  | 'marketExpansion'
  | 'acquisitionOnboarding'
  | 'platformArchitecture'
  // SLED / RAIN value-based care workbenches (one per spec workbench). Each
  // opens in workbench mode with the Cockpit pane docked on the right; Data
  // Sources reuses the existing slot. Additive: absent from the default slot
  // set and listed only by the RAIN personas.
  | 'valueInsights'
  | 'qualityGate'
  | 'lowValueCare'
  | 'modelGovernance'
  | 'countyExplorer'
  | 'rhtpReporting'
  | 'worklist'
  | 'scheduling'
  | 'reminders'
  | 'dataSources';
