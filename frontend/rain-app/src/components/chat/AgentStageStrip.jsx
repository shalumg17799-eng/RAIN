import { motion } from 'framer-motion';
import { Loader2, Check, RefreshCw, GitBranch, UserCheck, XCircle } from 'lucide-react';

// Live view of the supervisor-run agent pipeline for the in-flight question. Everything shown is
// built from the run's own typed SSE StageEvents (which never carry rows): the step list and
// counts come from graph_definition, the active agent and the reason it was picked come from
// supervisor_decision, fan-out branches carry their source/persona id, and the HITL hold shows as
// a waiting state until a reviewer (or the timeout) resolves it. Nothing here is hardcoded.
const prettify = (id) => String(id || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export const REASON_TEXT = {
  artifact_missing: 'next piece of the flow',
  intent_match: 'matches the routed intent',
  refine_requested: 'the assessor sent work back',
  refines_exhausted: 'refine budget spent — moving on',
  escalation: 'a stage escalated — finishing honestly',
  fanout_dispatch: 'one run per source',
  pipeline_complete: 'all stages done — composing',
  max_steps: 'step budget reached',
  goal_reached: 'finished',
};

export function foldStages(events) {
  const steps = [];
  const open = {};
  let plan = null;
  let pendingPick = null;
  const keyOf = (e) => `${e.step_id}${e.branch ? `@${e.branch}` : ''}`;
  for (const e of events || []) {
    if (e.type === 'graph_definition') {
      plan = { steps: e.steps, agent: e.agent_name, version: e.agent_version };
    } else if (e.type === 'supervisor_decision') {
      pendingPick = { skill: e.skill, stage: e.stage, reason: e.reason, considered: e.considered || [] };
    } else if (e.type === 'stage_started') {
      const step = {
        id: keyOf(e), stage: e.step_id, skill: e.skill, branch: e.branch || null,
        state: 'running', notes: [], attempt: e.attempt,
        pick: pendingPick && pendingPick.stage === e.step_id ? pendingPick : null,
      };
      open[keyOf(e)] = step;
      steps.push(step);
    } else if (e.type === 'stage_finished' && open[keyOf(e)]) {
      const step = open[keyOf(e)];
      step.state = 'done';
      step.label = e.label;
      step.ms = e.duration_ms;
      step.tokens = e.tokens ? (e.tokens.prompt_tokens || 0) + (e.tokens.completion_tokens || 0) : null;
    } else if (e.type === 'agent_iteration' && open[keyOf(e)]) {
      open[keyOf(e)].iteration = e.iteration;
    } else if (e.type === 'tool_call' && open[keyOf(e)]) {
      open[keyOf(e)].notes.push(`${e.tool}${e.status === 'ok' ? '' : ' ✗'}`);
    } else if (e.type === 'progress' && open[e.step_id]) {
      open[e.step_id].notes.push(e.count != null ? `${e.note}=${e.count}` : e.note);
    } else if (e.type === 'refine') {
      steps.push({ id: `refine-${e.attempt}`, skill: 'loop-back', state: 'done', label: e.label, refine: true });
    } else if (e.type === 'hitl_waiting') {
      const step = { id: `hitl-${steps.length}`, stage: e.step_id, skill: 'human review',
        state: 'waiting', hitl: true, reason: e.reason, notes: [] };
      open.__hitl = step;
      steps.push(step);
    } else if (e.type === 'hitl_decided' && open.__hitl) {
      open.__hitl.state = 'done';
      open.__hitl.label = e.label;
      delete open.__hitl;
    } else if (e.type === 'run_finished') {
      steps.push({ id: 'run', skill: 'run', state: 'done',
        label: `${e.outcome} in ${e.duration_ms} ms`, run: true });
    }
  }
  return { steps, plan };
}

export function hitlWaiting(events) {
  // the open HITL hold (if any): run_id + reason, so the chat can offer approve/edit/reject
  let waiting = null;
  for (const e of events || []) {
    if (e.type === 'hitl_waiting') waiting = { runId: e.run_id, reason: e.reason };
    else if (e.type === 'hitl_decided' || e.type === 'run_finished') waiting = null;
  }
  return waiting;
}

export default function AgentStageStrip({ events }) {
  const { steps, plan } = foldStages(events);
  if (!steps.length && !plan) return null;
  const stageCount = steps.filter((s) => s.state !== 'waiting' && !s.refine && !s.run).length;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      className="ml-11 mr-4 my-2 rounded-xl border border-[#003087]/10 bg-[#003087]/[0.03] px-4 py-2.5"
    >
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[#003087]/60 mb-1.5">
        Supervisor-run agent pipeline
        {plan && (
          <span className="normal-case font-normal tracking-normal text-[#003087]/40">
            {' '}· {plan.agent} v{plan.version} · {stageCount} of {plan.steps.length} stages
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {steps.map((s, i) => (
          <div key={s.id + i} className="flex items-center gap-1.5 text-[11px]">
            {i > 0 && <span className="text-gray-300">&rarr;</span>}
            {s.state === 'running'
              ? <Loader2 className="w-3 h-3 animate-spin text-[#003087]" />
              : s.state === 'waiting'
                ? <UserCheck className="w-3 h-3 animate-pulse text-amber-500" />
                : s.refine
                  ? <RefreshCw className="w-3 h-3 text-amber-500" />
                  : s.label === 'rejected' || s.label === 'escalate'
                    ? <XCircle className="w-3 h-3 text-red-500" />
                    : <Check className="w-3 h-3 text-emerald-600" />}
            <span className="font-medium text-gray-700">
              {prettify(s.stage) || s.skill || s.id}
              {s.branch && (
                <span className="text-[#003087]/60 font-normal">
                  {' '}<GitBranch className="inline w-2.5 h-2.5" /> {s.branch}
                </span>
              )}
            </span>
            {s.skill && s.stage && s.skill !== s.stage && !s.hitl && (
              <span className="text-gray-400">{s.skill}</span>
            )}
            {s.pick && (
              <span className="text-[#003087]/50 italic" title={`considered: ${s.pick.considered.join(', ')}`}>
                — {REASON_TEXT[s.pick.reason] || s.pick.reason}
              </span>
            )}
            {s.hitl && s.state === 'waiting' && (
              <span className="text-amber-600 font-medium">waiting ({prettify(s.reason)})</span>
            )}
            {s.iteration && <span className="text-gray-400">iter {s.iteration}</span>}
            {s.label && <span className="text-gray-400">{String(s.label)}</span>}
            {s.tokens != null && s.tokens > 0 && <span className="text-gray-300">{s.tokens} tok</span>}
            {s.notes && s.notes.length > 0 && <span className="text-gray-400/80 italic">({s.notes.join(', ')})</span>}
          </div>
        ))}
      </div>
    </motion.div>
  );
}
