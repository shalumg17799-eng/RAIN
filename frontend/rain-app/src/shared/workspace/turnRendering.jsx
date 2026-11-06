/**
 * What the workspace draws under an AI turn and in the right-hand context
 * panel. Split out of PersonaWorkspace.jsx to keep it under 400 lines; pure
 * functions of their inputs, behaviour unchanged.
 */
import { motion } from 'framer-motion';
import ActionCard from '@/components/cards/ActionCard';
import { contractComponents } from '@core/contract/spec';
import { answerNodes } from '@core/catalog/resolve';

/** The components under one AI turn: inline actions, root-cause tree, flow specs, the recorded answer. */
export function turnNodes(msg, { manifest, flows, briefing, RootCauseTree, intraday, answers, signals, confirmedActions, onConfirmAction }) {
  if (msg.role !== 'ai' || !msg.flowKey) return undefined;
  const out = [];

  // Inline-layout personas have no right context panel, so their recommended
  // actions compose into the chat thread at the action turn.
  if (manifest.layout === 'inline' && msg.flowKey === flows.actionTurnKey) {
    const actions = flows.chatFlows[flows.actionTurnKey]?.ui_components_to_render?.[0]?.actions || [];
    if (actions.length) {
      out.push(
        <div key="actions-inline" className="mt-3 space-y-3">
          <h4 className="text-sm font-semibold text-text">Recommended Actions</h4>
          {actions.map((action) => (
            <ActionCard key={action.id} action={action} onConfirm={onConfirmAction} isConfirmed={confirmedActions.has(action.id)} />
          ))}
        </div>,
      );
    }
  }

  // Root-cause correlation tree — rendered alongside the AI message that owns a
  // root-cause flow, using that step's snapshot highlight.
  if (briefing && RootCauseTree && briefing.rootCauseFlowKeys?.includes(msg.flowKey) && briefing.baseline.root_cause_tree) {
    const snap = briefing.baseline.per_step_snapshots?.[msg.flowKey];
    out.push(
      <div key="root-cause-inline" className="mt-3 rounded-xl border border-border bg-gradient-to-b from-surface-2 to-surface p-4">
        <h4 className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-text-muted mb-3">Root-Cause Correlation</h4>
        <RootCauseTree
          tree={briefing.baseline.root_cause_tree}
          highlight={snap?.treeHighlight || []}
          baseline={intraday.baseline}
          hoveredKpi={intraday.hoveredKpi}
          onHoverNode={intraday.setHoveredTreeNode}
        />
      </div>,
    );
  }

  // Components the turn carries in `{ type, props }` form: from the flow's
  // `ui_components_to_render`, or — over HTTP — everything the API sent.
  // Legacy flat entries are not drawn (see `isContractSpec`).
  const specs = contractComponents(msg.uiComponents);
  if (specs.length) out.push(...answerNodes(specs));

  // The persona's recorded answer — exactly what the recorded `POST /ask`
  // returns in `components[]`. Not for a turn that came from the API, which
  // already carried its components (drawing both would show every card twice).
  const answer = msg.remote ? undefined : answers?.(msg, signals);
  if (answer?.length) out.push(...answerNodes(answer));

  return out.length ? out : undefined;
}

/** The context panel's content for the current turn, or null. */
export function contextPanelContent({ contextPanel, currentTurn, flows, confirmedActions, onConfirmAction }) {
  if (!contextPanel) return null;
  const turns = Object.keys(contextPanel).map(Number);
  const maxTurn = Math.max(...turns);
  let Component = null;
  for (const [turnStr, comp] of Object.entries(contextPanel)) {
    const turn = Number(turnStr);
    if (currentTurn >= turn && (currentTurn < turn + 1 || turn === maxTurn)) Component = comp;
  }
  if (!Component) return null;

  if (Component === 'actions') {
    const actionsFlow = flows.chatFlows[flows.actionTurnKey];
    const actions = actionsFlow?.ui_components_to_render?.[0]?.actions || [];
    return (
      <motion.div key="actions" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }} className="space-y-3">
        <h3 className="text-sm font-semibold text-text mb-3">Recommended Actions</h3>
        {actions.map((action) => (
          <ActionCard key={action.id} action={action} onConfirm={onConfirmAction} isConfirmed={confirmedActions.has(action.id)} />
        ))}
      </motion.div>
    );
  }

  return (
    <motion.div key={`turn${currentTurn}`} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.3 }}>
      <Component />
    </motion.div>
  );
}
