/**
 * Sidebar nav slots. A persona lists the ones it shows (`features.navSlots`)
 * and may relabel them; a page guards itself by its slot (`usePageAccess`).
 *
 * Adding one takes three files in one change: this union, `NAV_SLOTS` in
 * components/layout/Sidebar.jsx, and the route in App.jsx.
 */

export type NavKey =
  | 'ask'
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
