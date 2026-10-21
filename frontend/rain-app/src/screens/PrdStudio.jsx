import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Loader2, CheckCircle2, XCircle, Circle, FileText, Play, Film,
  AlertTriangle, Users, HelpCircle, Table2, Network, ShieldCheck,
  Wrench, RotateCcw, FlaskConical,
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, LabelList,
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const NAVY = '#003087';

// Friendly names and descriptions per graph step id; anything unknown is prettified from its id,
// so the step list always comes from the GRAPH_DEFINITION event, never from hardcoded counts.
const STEP_META = {
  requirements: { title: 'Read the PRD', skill: 'Requirements Interpreter · AI agent',
    desc: 'Reads the whole document and lists the people it serves, their systems, problems and committed figures.' },
  questions_map: { title: 'Write their questions', skill: 'Persona Question Designer · AI agent, one run per persona',
    desc: 'Each persona gets its own agent run writing the questions they would ask.' },
  questions_reduce: { title: 'Merge the questions', skill: 'Deterministic reducer · no AI',
    desc: 'Merges and dedupes the per-persona registries, re-checks nothing was lost.' },
  entities: { title: 'Design the data tables', skill: 'Entity Model Designer · AI agent',
    desc: 'Designs the database tables needed to answer those questions.' },
  datamap: { title: 'Build the data map', skill: 'Deterministic build + audit · no AI',
    desc: 'Builds the connected map and audits it; near-miss names send the design back one step.' },
  scenario: { title: 'Design scenarios', skill: 'Scenario Designer · AI agent, synthetic data only',
    desc: 'Writes scenario SQL proposals against a synthetic database state. Never the live database.' },
  ontology_map: { title: 'Connect business concepts', skill: 'Upper Ontology Curator · AI agent, one run per persona',
    desc: 'Each persona’s concepts are curated separately and mapped onto the data map.' },
  ontology_reduce: { title: 'Merge the concept graph', skill: 'Deterministic reducer + audit · no AI',
    desc: 'Merges the persona slices, dedupes concepts, audits every edge; problems loop back.' },
  finalize: { title: 'Write the run report', skill: 'Deterministic · no AI',
    desc: 'Says honestly what ran, what looped back, and what needs human review.' },
};

const prettify = (id) =>
  id.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const stepFromId = (id) => ({
  id,
  title: STEP_META[id]?.title || prettify(id),
  skill: STEP_META[id]?.skill || 'Pipeline step',
  desc: STEP_META[id]?.desc || '',
  status: 'pending', activity: '', runs: 0, warn: '',
});

const firstName = (name) => {
  if (/patient/i.test(name)) return 'Patient';
  const parts = String(name).replace(/^Dr\.?\s*/i, '').split(/\s+/);
  return parts[0] || name;
};
const initials = (name) => firstName(name).slice(0, 2).toUpperCase();

function StatTile({ icon: Icon, value, label }) {
  return (
    <div className="flex-1 min-w-[120px] rounded-2xl border border-gray-100 bg-white px-4 py-3.5">
      <div className="flex items-center gap-2 text-[#003087]/60 mb-1">
        <Icon className="w-3.5 h-3.5" />
        <span className="text-[10px] font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-900 tabular-nums">{value ?? '—'}</div>
    </div>
  );
}

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-[11px] shadow-sm">
      <span className="font-semibold text-gray-800">{label}</span>
      <span className="text-gray-500"> · {payload[0].value}</span>
    </div>
  );
}

export default function PrdStudio() {
  const [steps, setSteps] = useState([]);
  const [agentInfo, setAgentInfo] = useState(null);
  const [running, setRunning] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [error, setError] = useState('');
  const [exitCode, setExitCode] = useState(null);
  const [art, setArt] = useState(null);
  const [personaFilter, setPersonaFilter] = useState('all');

  const esRef = useRef(null);
  const demoRef = useRef(false);

  const loadArtifacts = () => {
    fetch(`${API_BASE}/ultra/rain/prd/artifacts`)
      .then((r) => r.json())
      .then((d) => setArt(d && d.available ? d : null))
      .catch(() => setArt(null));
  };
  useEffect(() => { loadArtifacts(); return () => { if (esRef.current) esRef.current.close(); }; }, []);

  const patchStep = (id, patch) =>
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...(typeof patch === 'function' ? patch(s) : patch) } : s)));

  const handleEvent = (ev) => {
    if (ev.demo) demoRef.current = true;
    switch (ev.type) {
      case 'graph_definition':
        setAgentInfo({ name: ev.agent_name, version: ev.agent_version });
        setSteps(ev.steps.map(stepFromId));
        setIsDemo(Boolean(ev.demo));
        return;
      case 'stage_started':
        patchStep(ev.step_id, (s) => ({
          status: 'running', runs: s.runs + (ev.attempt ? 0 : 1),
          activity: ev.attempt ? `persona run ${ev.attempt + 1} started` : 'started',
        }));
        return;
      case 'agent_iteration':
        patchStep(ev.step_id, { status: 'running', activity: `agent thinking — iteration ${ev.iteration}` });
        return;
      case 'tool_call':
        patchStep(ev.step_id, {
          status: 'running',
          activity: `tool ${ev.tool} ${ev.status === 'ok' ? '✓' : 'failed'}`,
        });
        return;
      case 'progress':
        patchStep(ev.step_id, (s) => ({ activity: `${ev.note}${ev.count != null ? ` (${ev.count})` : ''}` }));
        return;
      case 'refine':
        patchStep(ev.step_id, {
          warn: `loop-back: ${ev.label} (attempt ${ev.attempt}) — the audit sent work back`,
        });
        return;
      case 'stage_finished':
        patchStep(ev.step_id, (s) => ({
          status: ev.label === 'escalate' ? 'failed' : 'done',
          activity: `${ev.label || 'done'} · ${(ev.duration_ms / 1000).toFixed(1)}s`
            + (s.runs > 1 ? ` · run ${s.runs}` : ''),
        }));
        return;
      case 'run_finished':
        if (ev.outcome === 'failed') setError('The run ended with a failure — see the run report.');
        return;
      default:
        return;
    }
  };

  const start = (demo) => {
    if (running) return;
    setSteps([]); setAgentInfo(null); setRunning(true); setError('');
    setExitCode(null); setIsDemo(demo); demoRef.current = demo;
    const es = new EventSource(`${API_BASE}/ultra/rain/prd/stream${demo ? '?demo=1' : ''}`);
    esRef.current = es;
    es.addEventListener('prd', (ev) => {
      try { handleEvent(JSON.parse(ev.data)); } catch { /* malformed event */ }
    });
    es.addEventListener('done', (ev) => {
      const payload = JSON.parse(ev.data);
      setExitCode(payload.exit_code); setRunning(false); es.close();
      if (!payload.demo && !demoRef.current) loadArtifacts();
    });
    es.addEventListener('error', (ev) => {
      if (ev.data) { try { setError(JSON.parse(ev.data).text); } catch { /* closed */ } }
      setRunning(false); es.close();
    });
  };

  const stepIcon = (s) => {
    if (s.status === 'running') return <Loader2 className="w-5 h-5 animate-spin text-[#003087]" />;
    if (s.status === 'done') return <CheckCircle2 className="w-5 h-5 text-emerald-600" />;
    if (s.status === 'failed') return <XCircle className="w-5 h-5 text-red-500" />;
    return <Circle className="w-5 h-5 text-gray-300" />;
  };

  const perPersona = (art?.personas || []).map((p) => ({
    name: firstName(p.name), questions: p.question_count,
  }));
  const EDGE_LABELS = {
    SERVES: 'Persona → concept', RELATES_TO: 'Concept → concept', MAPS_TO: 'Concept → data',
  };
  const edgeData = Object.entries(art?.ontology?.edge_counts || {}).map(([k, v]) => ({
    name: EDGE_LABELS[k] || k, count: v,
  }));
  const filteredQuestions = (art?.questions || []).filter(
    (q) => personaFilter === 'all' || q.persona_id === personaFilter,
  );
  const auditClean = art && art.ontology.unmapped_concepts === 0 && art.ontology.invalid_edges === 0;

  return (
    <div className="flex-1 overflow-y-auto scrollbar-sleek bg-gradient-to-b from-[#003087]/[0.02] to-white">
      <div className="max-w-4xl mx-auto px-6 py-8">

        {/* ─── header ─── */}
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#003087]/10 flex items-center justify-center flex-shrink-0">
            <FileText className="w-5 h-5 text-[#003087]" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">PRD Design Studio</h1>
            <p className="text-[13px] text-gray-500 leading-relaxed max-w-xl">
              A graph of AI agents reads the RAIN product document and designs the platform from it.
              Every step, loop-back, agent iteration and tool call below comes from the run&apos;s
              own typed events{agentInfo ? ` (${agentInfo.name} v${agentInfo.version})` : ''}.
            </p>
          </div>
        </div>

        {/* ─── run controls ─── */}
        <div className="flex flex-wrap items-center gap-2 mt-5">
          <button onClick={() => start(false)} disabled={running}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-[13px] font-semibold bg-[#003087] text-white hover:bg-[#002570] disabled:opacity-40 shadow-[0_2px_8px_rgba(0,48,135,0.3)]">
            <Play className="w-4 h-4" /> Run the real pipeline <span className="opacity-60 font-normal">~15 min</span>
          </button>
          <button onClick={() => start(true)} disabled={running}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-[13px] font-semibold border border-[#003087]/20 text-[#003087] hover:bg-[#003087]/5 disabled:opacity-40">
            <Film className="w-4 h-4" /> Replay last run&apos;s events
          </button>
        </div>

        {isDemo && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-[12.5px] text-amber-800 flex items-center gap-2 font-medium">
            <Film className="w-4 h-4 flex-shrink-0" />
            DEMO REPLAY — recorded events from the last real run, time-compressed. Nothing is being generated.
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" /> <span>The run stopped: {error}</span>
          </div>
        )}

        {/* the click must visibly do something before the first typed event arrives */}
        {running && steps.length === 0 && !error && (
          <div className="mt-6 rounded-2xl border border-[#003087]/20 bg-white px-5 py-4 flex items-center gap-3">
            <Loader2 className="w-5 h-5 animate-spin text-[#003087]" />
            <div>
              <p className="text-[13px] font-semibold text-gray-900">Starting the run…</p>
              <p className="text-[12px] text-gray-500">
                Loading the document and validating the agent graph — the live step list appears
                with the first event, usually within a few seconds. If nothing appears, the
                backend may be running old code and needs a restart.
              </p>
            </div>
          </div>
        )}

        {/* ─── step tracker, from the graph definition ─── */}
        {steps.length > 0 && (
          <div className="mt-6 space-y-2.5">
            {steps.map((s, i) => (
              <motion.div key={s.id} layout
                className={`rounded-2xl border px-5 py-3.5 bg-white ${
                  s.status === 'running' ? 'border-[#003087]/30 shadow-[0_2px_12px_rgba(0,48,135,0.08)]'
                  : s.status === 'done' ? 'border-emerald-100'
                  : s.status === 'failed' ? 'border-red-200' : 'border-gray-100'}`}>
                <div className="flex items-start gap-3">
                  <div className="mt-0.5">{stepIcon(s)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 flex-wrap">
                      <span className="text-[13.5px] font-semibold text-gray-900">
                        Step {i + 1} · {s.title}
                      </span>
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-[#003087]/50">{s.skill}</span>
                      {s.runs > 1 && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-50 rounded-full px-2 py-0.5">
                          <RotateCcw className="w-3 h-3" /> run {s.runs}
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] text-gray-500 mt-0.5">{s.desc}</p>
                    {s.activity && (
                      <p className={`text-[12px] mt-1 font-medium flex items-center gap-1.5 ${
                        s.status === 'done' ? 'text-emerald-700' : s.status === 'failed' ? 'text-red-600' : 'text-[#003087]'}`}>
                        {s.activity.startsWith('tool') && <Wrench className="w-3 h-3" />}
                        {s.activity}
                      </p>
                    )}
                    {s.warn && <p className="text-[12px] text-amber-600 mt-1">{s.warn}</p>}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {exitCode !== null && (
          <p className={`mt-3 text-[13px] font-semibold ${exitCode === 0 ? 'text-emerald-700' : 'text-red-600'}`}>
            {isDemo
              ? 'Demo replay finished. The results below are from the LAST REAL RUN, not this replay.'
              : exitCode === 0
                ? 'The pipeline finished. The results below are refreshed.'
                : `The pipeline exited with code ${exitCode}. A failed run can be resumed from its checkpoint.`}
          </p>
        )}

        {/* ════════════════════ RESULTS ════════════════════ */}
        {art && (
          <div className="mt-10">
            <div className="flex items-baseline justify-between flex-wrap gap-2">
              <h2 className="text-lg font-bold text-gray-900">What the AI designed from the PRD</h2>
              {art.generated_at && (
                <span className="text-[11px] text-gray-400">
                  from {art.source_document} · last run {new Date(art.generated_at).toLocaleString()}
                </span>
              )}
            </div>

            {/* stat tiles */}
            <div className="flex flex-wrap gap-3 mt-4">
              <StatTile icon={Users} value={art.personas.length} label="People served" />
              <StatTile icon={HelpCircle} value={art.questions.length} label="Questions written" />
              <StatTile icon={Table2} value={art.entity_model.table_count} label="Tables designed" />
              <StatTile icon={Network} value={art.ontology.concepts} label="Business concepts" />
              <StatTile icon={Network} value={art.ontology.edges} label="Connections" />
            </div>

            {/* audit banner */}
            <div className={`mt-3 rounded-xl px-4 py-2.5 flex items-center gap-2 text-[12.5px] font-medium ${
              auditClean ? 'bg-emerald-50 border border-emerald-100 text-emerald-700'
                         : 'bg-amber-50 border border-amber-100 text-amber-700'}`}>
              <ShieldCheck className="w-4 h-4 flex-shrink-0" />
              {auditClean
                ? 'Design audit clean — every concept has a definition and a mapping; nothing needs human review.'
                : `Design audit: ${art.ontology.unmapped_concepts} concept(s) and ${art.ontology.invalid_edges} connection(s) flagged for human review.`}
            </div>

            {art.scenario?.present && (
              <div className="mt-2 rounded-xl px-4 py-2.5 flex items-center gap-2 text-[12.5px] font-medium bg-violet-50 border border-violet-100 text-violet-700">
                <FlaskConical className="w-4 h-4 flex-shrink-0" />
                {art.scenario.count} scenario(s) designed against a SYNTHETIC database state
                ({art.scenario.db_state_source || 'generated from the entity model'}) — never the live database.
              </div>
            )}

            {/* persona cards */}
            <h3 className="text-[13px] font-bold text-gray-900 mt-7 mb-3">
              The people the PRD designs for
              <span className="font-normal text-gray-400"> — found by reading the document, not hardcoded</span>
            </h3>
            <div className="grid sm:grid-cols-2 gap-3">
              {art.personas.map((p) => (
                <div key={p.id} className="rounded-2xl border border-gray-100 bg-white px-4 py-3.5">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-xl bg-[#003087] text-white flex items-center justify-center text-[11px] font-bold flex-shrink-0">
                      {initials(p.name)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-gray-900 truncate">
                        {p.name}
                        {p.is_default && <span className="ml-1.5 text-[9px] font-bold uppercase tracking-wider text-[#003087]/60">default</span>}
                      </p>
                      <p className="text-[11px] text-gray-500 truncate">{p.role}</p>
                    </div>
                    <span className="ml-auto flex-shrink-0 text-[10px] font-semibold text-[#003087] bg-[#003087]/5 rounded-full px-2 py-0.5">
                      {p.question_count} questions
                    </span>
                  </div>
                  {p.problems.length > 0 && (
                    <ul className="mt-2.5 space-y-1">
                      {p.problems.slice(0, 2).map((pr, i) => (
                        <li key={i} className="text-[11.5px] text-gray-500 leading-snug pl-3 relative">
                          <span className="absolute left-0 text-[#003087]/40">—</span>{pr}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>

            {/* charts row */}
            <div className="grid md:grid-cols-2 gap-4 mt-6">
              <div className="rounded-2xl border border-gray-100 bg-white px-4 py-4">
                <p className="text-[12.5px] font-bold text-gray-900 mb-2">Questions written per person</p>
                <ResponsiveContainer width="100%" height={perPersona.length * 34 + 10}>
                  <BarChart data={perPersona} layout="vertical" margin={{ left: 0, right: 28, top: 0, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" width={64} axisLine={false} tickLine={false}
                      tick={{ fontSize: 11, fill: '#6b7280' }} />
                    <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(0,48,135,0.04)' }} />
                    <Bar dataKey="questions" fill={NAVY} radius={[0, 4, 4, 0]} barSize={14}>
                      <LabelList dataKey="questions" position="right" style={{ fontSize: 11, fill: '#374151' }} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="rounded-2xl border border-gray-100 bg-white px-4 py-4">
                <p className="text-[12.5px] font-bold text-gray-900 mb-2">How the design connects together</p>
                <ResponsiveContainer width="100%" height={edgeData.length * 34 + 10}>
                  <BarChart data={edgeData} layout="vertical" margin={{ left: 0, right: 28, top: 0, bottom: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="name" width={128} axisLine={false} tickLine={false}
                      tick={{ fontSize: 11, fill: '#6b7280' }} />
                    <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(0,48,135,0.04)' }} />
                    <Bar dataKey="count" fill={NAVY} radius={[0, 4, 4, 0]} barSize={14}>
                      <LabelList dataKey="count" position="right" style={{ fontSize: 11, fill: '#374151' }} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <p className="text-[10.5px] text-gray-400 mt-1.5">
                  {art.entity_model.table_count} tables designed
                  {art.entity_model.new_tables?.length ? ` — ${art.entity_model.new_tables.length} newly proposed beyond today's database` : ''}.
                </p>
              </div>
            </div>

            {/* question explorer */}
            <div className="rounded-2xl border border-gray-100 bg-white mt-6">
              <div className="px-4 pt-4">
                <p className="text-[12.5px] font-bold text-gray-900">Every question, by person</p>
                <div className="flex flex-wrap gap-1.5 mt-2.5 mb-3">
                  <button onClick={() => setPersonaFilter('all')}
                    className={`px-3 py-1 rounded-full text-[11px] font-medium border ${
                      personaFilter === 'all' ? 'bg-[#003087] text-white border-[#003087]' : 'border-gray-200 text-gray-600 hover:border-[#003087]/30'}`}>
                    All ({art.questions.length})
                  </button>
                  {art.personas.map((p) => (
                    <button key={p.id} onClick={() => setPersonaFilter(p.id)}
                      className={`px-3 py-1 rounded-full text-[11px] font-medium border ${
                        personaFilter === p.id ? 'bg-[#003087] text-white border-[#003087]' : 'border-gray-200 text-gray-600 hover:border-[#003087]/30'}`}>
                      {firstName(p.name)} ({p.question_count})
                    </button>
                  ))}
                </div>
              </div>
              <div className="max-h-72 overflow-y-auto scrollbar-sleek border-t border-gray-50">
                <table className="w-full text-[12px]">
                  <tbody>
                    {filteredQuestions.map((q, i) => (
                      <tr key={i} className="border-b border-gray-50 last:border-0">
                        <td className="px-4 py-2 text-gray-700 leading-snug">{q.text}</td>
                        <td className="px-3 py-2 w-24 align-top">
                          <span className={`inline-block text-[9.5px] font-semibold uppercase tracking-wider rounded-full px-2 py-0.5 ${
                            q.tier === 'extracted' ? 'bg-[#003087]/5 text-[#003087]' : 'bg-gray-100 text-gray-500'}`}>
                            {q.tier === 'extracted' ? 'From PRD' : 'Suggested'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {!art && (
          <p className="mt-10 text-[13px] text-gray-400">
            No design artifacts found yet — run the pipeline to produce them.
          </p>
        )}
      </div>
    </div>
  );
}
