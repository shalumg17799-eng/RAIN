import { motion } from 'framer-motion';
import { Loader2, Check, RefreshCw } from 'lucide-react';

// Live view of the governed agent's pipeline for the in-flight question:
// route -> metadata/sliver -> generate -> execute -> assess -> compose.
// Built from the engine's SSE StageEvents (which never carry rows).
const STEP_TITLES = {
  route: 'Route',
  metadata_answer: 'Graph lookup',
  sliver: 'Schema sliver',
  generate: 'Generate SQL',
  execute: 'Governed execute',
  assess: 'Assess',
  compose: 'Compose',
};

export function foldStages(events) {
  const steps = [];
  const open = {};
  for (const e of events || []) {
    if (e.type === 'stage_started') {
      const step = { id: e.step_id, skill: e.skill, state: 'running', notes: [], attempt: e.attempt };
      open[e.step_id] = step;
      steps.push(step);
    } else if (e.type === 'stage_finished' && open[e.step_id]) {
      open[e.step_id].state = 'done';
      open[e.step_id].label = e.label;
      open[e.step_id].ms = e.duration_ms;
    } else if (e.type === 'progress' && open[e.step_id]) {
      open[e.step_id].notes.push(e.count != null ? `${e.note}=${e.count}` : e.note);
    } else if (e.type === 'refine') {
      steps.push({ id: `refine-${e.attempt}`, skill: 'refine loop', state: 'done', label: e.label, refine: true });
    } else if (e.type === 'run_finished') {
      steps.push({ id: 'run', skill: 'run', state: 'done', label: `${e.outcome} in ${e.duration_ms} ms`, run: true });
    }
  }
  return steps;
}

export default function AgentStageStrip({ events }) {
  const steps = foldStages(events);
  if (!steps.length) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      className="ml-11 mr-4 my-2 rounded-xl border border-[#003087]/10 bg-[#003087]/[0.03] px-4 py-2.5"
    >
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[#003087]/60 mb-1.5">
        Governed agent pipeline
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {steps.map((s, i) => (
          <div key={s.id + i} className="flex items-center gap-1.5 text-[11px]">
            {i > 0 && <span className="text-gray-300">&rarr;</span>}
            {s.state === 'running'
              ? <Loader2 className="w-3 h-3 animate-spin text-[#003087]" />
              : s.refine
                ? <RefreshCw className="w-3 h-3 text-amber-500" />
                : <Check className="w-3 h-3 text-emerald-600" />}
            <span className="font-medium text-gray-700">{STEP_TITLES[s.id] || s.skill || s.id}</span>
            {s.label && <span className="text-gray-400">{String(s.label)}</span>}
            {s.notes && s.notes.length > 0 && <span className="text-gray-400/80 italic">({s.notes.join(', ')})</span>}
          </div>
        ))}
      </div>
    </motion.div>
  );
}
