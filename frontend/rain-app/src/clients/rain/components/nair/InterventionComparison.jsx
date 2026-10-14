import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';

// The original static card, kept as the offline fallback.
const STATIC_OPTIONS = [
  { id: 'A', name: 'Mobile Obstetric Outreach', reach: '84% of displaced cohort', timeline: '30 days', funding: 'Flex Fund', priority: 'Infrastructure', recommended: true },
  { id: 'B', name: 'Telehealth Connectivity Bridge', reach: '240 dead-zone patients', timeline: '60 days', funding: 'RHOAP', priority: 'Value-based', recommended: true },
  { id: 'C', name: 'Care Continuity Restoration', reach: '64% of avoidable ED', timeline: '90 days', funding: '$1.0M avoided', priority: 'Cost & quality', recommended: false },
];

function OptionRow({ o }) {
  return (
    <div className={`rounded-lg border p-2.5 ${o.recommended ? 'bg-white' : 'bg-white/60 border-gray-100'}`} style={o.recommended ? { borderColor: RAIN_NAVY } : {}}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-5 h-5 rounded flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0" style={{ backgroundColor: o.recommended ? RAIN_NAVY : '#94a3b8' }}>{o.id}</span>
        <p className="text-[11px] font-semibold text-gray-800 flex-1">{o.name}</p>
        {o.recommended && <span className="text-[8px] font-bold text-white px-1.5 py-0.5 rounded uppercase" style={{ backgroundColor: RAIN_NAVY }}>Recommended</span>}
      </div>
      <div className="grid grid-cols-4 gap-1.5 pl-7">
        <div><p className="text-[8px] uppercase text-gray-400 font-semibold">Reach</p><p className="text-[9px] font-semibold text-gray-700 leading-tight">{o.reach}</p></div>
        <div><p className="text-[8px] uppercase text-gray-400 font-semibold">Timeline</p><p className="text-[9px] font-semibold text-gray-700">{o.timeline}</p></div>
        <div><p className="text-[8px] uppercase text-gray-400 font-semibold">Funding</p><p className="text-[9px] font-semibold text-gray-700">{o.funding}</p></div>
        <div><p className="text-[8px] uppercase text-gray-400 font-semibold">Priority</p><p className="text-[9px] font-semibold" style={{ color: RAIN_NAVY }}>{o.priority}</p></div>
      </div>
    </div>
  );
}

export function StaticInterventionComparison() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">RHTP-Aligned Intervention Options</p>
        <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded">A + B in parallel</span>
      </div>
      <div className="space-y-2">{STATIC_OPTIONS.map((o) => <OptionRow key={o.id} o={o} />)}</div>
      <p className="text-[10px] text-gray-400 mt-2">All three map to Make Rural Nevada Healthy Again — one coherent initiative, three funding streams.</p>
    </motion.div>
  );
}

// Live: reach figures come from the backend on each load, computed from
// rain.db. Corrects the static card's unsupported 84% (real: 48 patients)
// and 240 (real: 3 dead-zone sessions, 574 broader no-broadband population),
// and drops the fabricated $1.0M cost claim -- see priya_intervention_comparison.py.
export default function InterventionComparison() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('InterventionComparison', 'priya')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticInterventionComparison />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Comparing intervention options…</div>;
  }

  const recommendedIds = data.options.filter((o) => o.recommended).map((o) => o.id).join(' + ');
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">RHTP-Aligned Intervention Options</p>
        {recommendedIds && <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded">{recommendedIds} in parallel</span>}
      </div>
      <div className="space-y-2">{data.options.map((o) => <OptionRow key={o.id} o={o} />)}</div>
      <p className="text-[9px] text-gray-400 mt-2 leading-snug">{data.note}</p>
    </motion.div>
  );
}
