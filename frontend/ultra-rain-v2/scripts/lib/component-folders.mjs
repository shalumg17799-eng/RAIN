/**
 * The move from client-named component folders to purpose-named ones
 * (Nov 2026): old folder → new folder, and the client that owns each new
 * folder. Kept as the record of the move (and its alias table for anyone with
 * an old path in a branch); `tenants.config.json` → `componentOwners` is the
 * live ownership list that lint, the audit and the scaffolds read.
 */
export const FOLDER_MOVES = [
  // [old folder under src/components, new folder, owning client]
  ['amisa/director', 'school-benchmarks/director', 'amisa'],
  ['amisa/hr', 'school-benchmarks/school-hr', 'amisa'],
  ['amisa/shared', 'school-benchmarks/shared', 'amisa'],
  ['aramco/pages', 'site-safety/pages', 'aramco'],
  ['aramco', 'site-safety', 'aramco'],
  ['att/pages', 'billing-operations/pages', 'att'],
  ['att', 'billing-operations', 'att'],
  ['doit/author', 'surveys/author', 'doit'],
  ['doit/admin', 'surveys/admin', 'doit'],
  ['doit/resident', 'surveys/resident', 'doit'],
  ['doit/shared', 'surveys/shared', 'doit'],
  ['esfcu/shared/presentation', 'decks/board-deck-engine', 'esfcu'],
  ['esfcu/shared', 'leadership/briefing-shared', 'esfcu'],
  ['esfcu/ceo/presentation/slides', 'decks/merger-board-deck/slides', 'esfcu'],
  ['esfcu/ceo/presentation', 'decks/merger-board-deck', 'esfcu'],
  ['esfcu/ceo/performance', 'leadership/merger-integration/performance', 'esfcu'],
  ['esfcu/ceo', 'leadership/merger-integration', 'esfcu'],
  ['esfcu/cro/presentation/slides', 'decks/fraud-risk-deck/slides', 'esfcu'],
  ['esfcu/cro/presentation', 'decks/fraud-risk-deck', 'esfcu'],
  ['esfcu/cro', 'fraud/member-fraud-risk', 'esfcu'],
  ['esfcu/pages', 'fraud/member-fraud-risk/pages', 'esfcu'],
  ['esfcu', 'leadership/briefing-shared', 'esfcu'],
  ['lyte-fiber/planning', 'network-intelligence/planning', 'lyte_fiber'],
  ['lyte-fiber/foundation', 'network-intelligence/foundation', 'lyte_fiber'],
  ['lyte-fiber/shared', 'network-intelligence/shared', 'lyte_fiber'],
  ['lyte-fiber/map', 'network-intelligence/map', 'lyte_fiber'],
  ['lyte-fiber/cx', 'network-intelligence/churn', 'lyte_fiber'],
  ['lyte-fiber/revenue', 'network-intelligence/revenue', 'lyte_fiber'],
  ['lyte-fiber/pages', 'network-intelligence/pages', 'lyte_fiber'],
  ['md-comptroller/stages', 'tax-agency/campaign-stages', 'md_comptroller'],
  ['md-comptroller/fraud', 'tax-agency/refund-fraud', 'md_comptroller'],
  ['md-comptroller/shared', 'tax-agency/shared', 'md_comptroller'],
  ['md-comptroller/architecture', 'tax-agency/architecture', 'md_comptroller'],
  ['md-comptroller/protection', 'tax-agency/protection', 'md_comptroller'],
  ['md-comptroller/warehouse', 'tax-agency/warehouse', 'md_comptroller'],
  ['md-comptroller/pages', 'tax-agency/pages', 'md_comptroller'],
  ['md-comptroller/revops', 'tax-agency/revenue-operations', 'md_comptroller'],
  ['newfold/quality', 'contact-center/brand-care/quality', 'newfold_digital'],
  ['newfold/director', 'contact-center/brand-care/director', 'newfold_digital'],
  ['newfold/workforce', 'contact-center/brand-care/workforce', 'newfold_digital'],
  ['newfold/ops', 'contact-center/brand-care/operations', 'newfold_digital'],
  ['newfold', 'contact-center/brand-care', 'newfold_digital'],
  ['nfcu/confidence', 'ai-governance/confidence', 'nfcu'],
  ['nfcu/member', 'contact-center/member-self-service', 'nfcu'],
  ['nfcu/agent', 'contact-center/agent-assist', 'nfcu'],
  ['nfcu/feedback', 'contact-center/message-feedback', 'nfcu'],
  ['nfcu/platform-admin/observability', 'ai-governance/platform-admin/observability', 'nfcu'],
  ['nfcu/platform-admin', 'ai-governance/platform-admin', 'nfcu'],
  ['nfcu/governance', 'ai-governance/model-governance', 'nfcu'],
  ['nfcu', 'contact-center/workforce-analytics', 'nfcu'],
  ['penfed/capmarkets', 'finance/capital-markets', 'penfed'],
  ['rain/workbenches', 'value-based-care/workbenches', 'rain'],
  ['rain/shell', 'value-based-care/shell', 'rain'],
  ['rain/cards', 'value-based-care/cards', 'rain'],
  ['rain/patient', 'value-based-care/patient', 'rain'],
  ['rain/pages', 'value-based-care/pages', 'rain'],
  ['sclac/cards', 'court-performance/cards', 'sclac'],
  ['sclac/transformation', 'court-performance/transformation', 'sclac'],
  ['sclac/shared', 'court-performance/shared', 'sclac'],
  ['sclac/briefing/slides', 'decks/court-kpi-deck/slides', 'sclac'],
  ['sclac/briefing', 'decks/court-kpi-deck', 'sclac'],
  ['sclac/kpi/viz', 'court-performance/kpi/viz', 'sclac'],
  ['sclac/kpi/cx', 'court-performance/kpi/cx', 'sclac'],
  ['sclac/kpi', 'court-performance/kpi', 'sclac'],
  ['sclac/pages', 'court-performance/pages', 'sclac'],
  ['ussfcu/evelyn', 'compliance/population-review', 'ussfcu'],
  ['ussfcu/nadia', 'compliance/file-review', 'ussfcu'],
  ['ussfcu/compliance', 'compliance/disclosures', 'ussfcu'],
  ['ussfcu/cfo', 'finance/reconciliation-close', 'ussfcu'],
  ['ussfcu/finance/pages', 'finance/shutdown-scenarios/pages', 'ussfcu'],
  ['ussfcu/finance', 'finance/shutdown-scenarios', 'ussfcu'],
  ['ussfcu/ceo/presentation/slides', 'decks/liquidity-board-deck/slides', 'ussfcu'],
  ['ussfcu/ceo/presentation', 'decks/liquidity-board-deck', 'ussfcu'],
  ['ussfcu/ceo/performance', 'leadership/liquidity-watch/performance', 'ussfcu'],
  ['ussfcu/ceo', 'leadership/liquidity-watch', 'ussfcu'],
];

/** Old folder → new folder for a path under src/components (longest match wins). */
export function movedPath(rel) {
  const hit = [...FOLDER_MOVES].sort((a, b) => b[0].length - a[0].length).find(([from]) => rel === from || rel.startsWith(`${from}/`));
  return hit ? hit[1] + rel.slice(hit[0].length) : null;
}

/**
 * The client that owns a path under src/components (`site-safety/MusterBoard.jsx`),
 * by the longest folder in `owners` (tenants.config.json → componentOwners), or
 * null for the shared library.
 */
export function componentOwner(rel, owners) {
  const hit = Object.keys(owners).sort((a, b) => b.length - a.length).find((d) => rel === d || rel.startsWith(`${d}/`));
  return hit ? owners[hit] : null;
}

/** A client's data or market folder name (`lyte-fiber`) → its client id (`lyte_fiber`). */
export const clientOfFolder = (folder) => folder.replace(/-/g, '_');
