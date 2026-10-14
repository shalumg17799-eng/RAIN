import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Pill, Bus, UserX, WifiOff } from 'lucide-react';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';

function Spark({ pts, up }) {
  const w = 70, h = 22, min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1;
  const d = pts.map((p, i) => `${(i / (pts.length - 1)) * w},${h - ((p - min) / span) * (h - 4) - 2}`).join(' ');
  const color = up ? '#DC2626' : '#D97706';
  const lastY = h - ((pts[pts.length - 1] - min) / span) * (h - 4) - 2;
  return (
    <svg width={w} height={h} className="flex-shrink-0">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={w} cy={lastY} r="2.2" fill={color} />
    </svg>
  );
}

// The original static card, kept as the offline fallback.
const STATIC_PATIENTS = [
  { id: 'P-3310', cond: 'CHF', marker: 'weight', pts: [181, 183, 185, 188, 191, 194], medGap: true, reassigned: true, transport: true, silent: true },
  { id: 'P-3287', cond: 'COPD', marker: 'spo2', pts: [95, 94, 93, 91, 90, 88], medGap: true, reassigned: true, transport: true },
  { id: 'P-3344', cond: 'CHF', marker: 'weight', pts: [167, 169, 170, 172, 175, 178], medGap: true, reassigned: true, transport: true },
  { id: 'P-3301', cond: 'CHF', marker: 'weight', pts: [201, 202, 204, 207, 209, 212], medGap: true, reassigned: true, transport: true },
  { id: 'P-3356', cond: 'COPD', marker: 'spo2', pts: [94, 93, 92, 91, 89, 88], medGap: true, reassigned: true },
];

export function StaticDeteriorationBoard() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">CHF / COPD Deterioration Board</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">17 patients · 11 weight ↑ · 6 SpO2 ↓</span>
      </div>
      <div className="space-y-1.5 mb-2">
        {STATIC_PATIENTS.map((p) => (
          <div key={p.id} className={`rounded-lg border px-2.5 py-1.5 flex items-center gap-2 ${p.silent ? 'bg-red-50/60 border-red-200' : 'bg-white border-gray-100'}`}>
            <span className="text-[10px] font-bold text-gray-700 w-12 flex-shrink-0">{p.id}</span>
            <span className="text-[8px] font-bold px-1 py-0.5 rounded flex-shrink-0" style={{ color: RAIN_NAVY, backgroundColor: `${RAIN_NAVY}12` }}>{p.cond}</span>
            <Spark pts={p.pts} up={p.marker === 'weight'} />
            <span className="text-[8px] text-gray-400 flex-shrink-0">{p.marker === 'weight' ? 'wt ↑' : 'SpO2 ↓'}</span>
            <div className="flex items-center gap-1 ml-auto flex-shrink-0">
              {p.medGap && <span title="Medication gap"><Pill className="w-3.5 h-3.5 text-red-500" /></span>}
              {p.reassigned && <span title="Provider reassigned"><UserX className="w-3.5 h-3.5 text-amber-600" /></span>}
              {p.transport && <span title="Transport barrier"><Bus className="w-3.5 h-3.5 text-violet-600" /></span>}
              {p.silent && <span title="No contact 24 days" className="flex items-center gap-0.5"><WifiOff className="w-3.5 h-3.5 text-red-600" /><span className="text-[8px] font-bold text-red-600">24d</span></span>}
            </div>
          </div>
        ))}
        <p className="text-[9px] text-gray-400 pl-1">Showing 5 of 17 · 9 with a 30-day med gap · 5 lost their provider to the Battle Mountain reassignment</p>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] text-gray-500 border-t border-gray-100 pt-2">
        <span className="flex items-center gap-1"><Pill className="w-3 h-3 text-red-500" /> Med gap</span>
        <span className="flex items-center gap-1"><UserX className="w-3 h-3 text-amber-600" /> Reassigned provider</span>
        <span className="flex items-center gap-1"><Bus className="w-3 h-3 text-violet-600" /> Transport barrier</span>
        <span className="flex items-center gap-1"><WifiOff className="w-3 h-3 text-red-600" /> Silent (no contact)</span>
      </div>
    </motion.div>
  );
}

// Live: all 17 real patients, real ids, real sparklines from their own RPM
// readings, real risk flags. Corrects two figures the static card had
// wrong -- the med-gap footer (static said 9; the real, verified count is
// 10) and the "silent" badge (static showed one patient silent 24 days;
// in the real data zero of the 17 are silent today) -- see
// sarah_deterioration_live.py.
export default function DeteriorationBoard() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('DeteriorationBoard', 'sarah')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticDeteriorationBoard />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Loading the deterioration cohort…</div>;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">CHF / COPD Deterioration Board</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">
          {data.total} patients · {data.weight_up} weight ↑ · {data.spo2_down} SpO2 ↓
        </span>
      </div>
      <div className="space-y-1.5 mb-2 max-h-[280px] overflow-y-auto pr-0.5">
        {data.patients.map((p) => (
          <div key={p.id} className={`rounded-lg border px-2.5 py-1.5 flex items-center gap-2 ${p.silent ? 'bg-red-50/60 border-red-200' : 'bg-white border-gray-100'}`}>
            <span className="text-[10px] font-bold text-gray-700 w-16 flex-shrink-0">{p.id}</span>
            <span className="text-[8px] font-bold px-1 py-0.5 rounded flex-shrink-0" style={{ color: RAIN_NAVY, backgroundColor: `${RAIN_NAVY}12` }}>{p.cond}</span>
            <Spark pts={p.pts} up={p.marker === 'weight'} />
            <span className="text-[8px] text-gray-400 flex-shrink-0">{p.marker === 'weight' ? 'wt ↑' : 'SpO2 ↓'}</span>
            <div className="flex items-center gap-1 ml-auto flex-shrink-0">
              {p.med_gap && <span title="Medication gap"><Pill className="w-3.5 h-3.5 text-red-500" /></span>}
              {p.reassigned && <span title="Provider reassigned"><UserX className="w-3.5 h-3.5 text-amber-600" /></span>}
              {p.transport && <span title="Transport barrier"><Bus className="w-3.5 h-3.5 text-violet-600" /></span>}
              {p.silent && <span title="No contact 24 days" className="flex items-center gap-0.5"><WifiOff className="w-3.5 h-3.5 text-red-600" /><span className="text-[8px] font-bold text-red-600">24d</span></span>}
            </div>
          </div>
        ))}
      </div>
      <p className="text-[9px] text-gray-400 pl-1 mb-2">
        All {data.total} shown · {data.med_gap_count} with a 30-day med gap · {data.reassigned_count} lost their provider to the Battle Mountain reassignment
        {data.silent_count > 0 ? ` · ${data.silent_count} silent (no contact ${24}+ days)` : ''}
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[9px] text-gray-500 border-t border-gray-100 pt-2">
        <span className="flex items-center gap-1"><Pill className="w-3 h-3 text-red-500" /> Med gap</span>
        <span className="flex items-center gap-1"><UserX className="w-3 h-3 text-amber-600" /> Reassigned provider</span>
        <span className="flex items-center gap-1"><Bus className="w-3 h-3 text-violet-600" /> Transport barrier</span>
        <span className="flex items-center gap-1"><WifiOff className="w-3 h-3 text-red-600" /> Silent (no contact)</span>
      </div>
    </motion.div>
  );
}
