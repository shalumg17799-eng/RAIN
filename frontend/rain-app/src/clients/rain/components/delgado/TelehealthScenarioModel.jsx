import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';
const EMERALD = '#059669';
const RED = '#DC2626';

// The original static card, kept as the offline fallback.
const STATIC_ASSIGNMENTS = [
  { label: 'Telehealth', count: 8, note: 'Adequate broadband — virtual monitoring', color: EMERALD },
  { label: 'Hybrid + NEMT', count: 3, note: 'Virtual + 1 in-person visit', color: RAIN_NAVY },
  { label: 'In-person only', count: 3, note: 'Broadband-dead — highest priority', color: RED },
];
const days = ['Now', '+10d', '+20d', '+30d'];
const intervention = [61, 72, 82, 88];
const noAction = [61, 59, 57, 55];
const VB_W = 300, VB_H = 150, L = 30, R = 292, T = 12, B = 116, Y_MIN = 50, Y_MAX = 95;
const xAt = (i) => L + ((R - L) / (days.length - 1)) * i;
const yAt = (v) => B - ((v - Y_MIN) / (Y_MAX - Y_MIN)) * (B - T);
const toPts = (arr) => arr.map((v, i) => `${xAt(i)},${yAt(v)}`).join(' ');
const gridVals = [60, 70, 80, 90];

export function StaticTelehealthScenarioModel() {
  const areaPath = `M ${xAt(0)},${B} L ${toPts(intervention).replace(/ /g, ' L ')} L ${xAt(days.length - 1)},${B} Z`;
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-semibold text-gray-600">Prenatal Completion — 30-Day Projection</p>
        <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded">+27 pts vs. no action</span>
      </div>
      <p className="text-[10px] text-gray-400 mb-2">Telehealth for 8 + hybrid for 3 recovers the cohort from 61% to a projected 88%.</p>
      <div className="bg-white rounded-lg border border-gray-100 p-2.5 mb-3">
        <svg viewBox={`0 0 ${VB_W} ${VB_H}`} className="w-full" style={{ height: 'auto' }}>
          <defs><linearGradient id="telehealthArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={EMERALD} stopOpacity="0.18" /><stop offset="1" stopColor={EMERALD} stopOpacity="0.01" /></linearGradient></defs>
          {gridVals.map((v) => (<g key={v}><line x1={L} y1={yAt(v)} x2={R} y2={yAt(v)} stroke="#EEF1F4" strokeWidth="1" /><text x={L - 5} y={yAt(v) + 3} textAnchor="end" fill="#94A3B8" style={{ fontSize: 8 }}>{v}%</text></g>))}
          <path d={areaPath} fill="url(#telehealthArea)" />
          <polyline points={toPts(noAction)} fill="none" stroke={RED} strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" strokeLinejoin="round" />
          <polyline points={toPts(intervention)} fill="none" stroke={EMERALD} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx={xAt(0)} cy={yAt(61)} r="3" fill="#fff" stroke={RAIN_NAVY} strokeWidth="2" />
          <text x={xAt(0) + 1} y={yAt(61) - 6} textAnchor="start" fill={RAIN_NAVY} style={{ fontSize: 9, fontWeight: 700 }}>61%</text>
          <circle cx={xAt(3)} cy={yAt(88)} r="3.2" fill={EMERALD} />
          <text x={xAt(3)} y={yAt(88) - 6} textAnchor="end" fill={EMERALD} style={{ fontSize: 10, fontWeight: 700 }}>88%</text>
          <circle cx={xAt(3)} cy={yAt(55)} r="3" fill="#fff" stroke={RED} strokeWidth="2" />
          <text x={xAt(3)} y={yAt(55) + 12} textAnchor="end" fill={RED} style={{ fontSize: 9, fontWeight: 700 }}>55%</text>
          {days.map((d, i) => (<text key={d} x={xAt(i)} y={B + 14} textAnchor={i === 0 ? 'start' : i === days.length - 1 ? 'end' : 'middle'} fill="#94A3B8" style={{ fontSize: 8 }}>{d}</text>))}
        </svg>
        <div className="flex items-center gap-4 mt-1 pl-1">
          <span className="flex items-center gap-1.5 text-[9.5px] text-gray-600"><span className="w-3.5 h-[3px] rounded-full" style={{ backgroundColor: EMERALD }} /> With intervention</span>
          <span className="flex items-center gap-1.5 text-[9.5px] text-gray-600"><span className="w-3.5 h-[3px] rounded-full" style={{ background: 'repeating-linear-gradient(90deg,#DC2626 0 3px,transparent 3px 6px)' }} /> No action</span>
        </div>
      </div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1.5">Patient-by-patient assignment (14 third-trimester)</p>
      <div className="grid grid-cols-3 gap-2">
        {STATIC_ASSIGNMENTS.map((a) => (
          <div key={a.label} className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center gap-1.5 mb-0.5"><span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: a.color }} /><p className="text-[15px] font-bold leading-none" style={{ color: a.color }}>{a.count}</p></div>
            <p className="text-[9.5px] font-semibold text-gray-700">{a.label}</p>
            <p className="text-[8.5px] text-gray-400 leading-tight mt-0.5">{a.note}</p>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// Live: the patient assignment split comes from the backend, shared with
// Maria's action package. The static card's 30-day forecast is dropped
// (no forecasting model exists in the dataset) and replaced with the real
// documented trend plus today's live snapshot -- which disagree with each
// other, shown rather than hidden. See maria_telehealth_scenario.py.
export default function TelehealthScenarioModel() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('TelehealthScenario', 'maria')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticTelehealthScenarioModel />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Loading telehealth assignment and trend data…</div>;
  }

  const dt = data.documented_trend, live = data.live_snapshot;
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-semibold text-gray-600">Prenatal Completion — Documented Trend vs. Today</p>
        {data.discrepancy && (
          <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-100 px-1.5 py-0.5 rounded">figures disagree</span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3 mt-2">
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[18px] font-bold" style={{ color: RAIN_NAVY }}>{dt.before}% → {dt.after}%</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Documented trend ({dt.before_date} → {dt.after_date})</p>
        </div>
        <div className="bg-white rounded-lg p-2.5 border border-gray-100 text-center">
          <p className="text-[18px] font-bold text-emerald-600">{live.value}%</p>
          <p className="text-[9px] text-gray-500 leading-tight mt-0.5">Live snapshot, computed as of {live.as_of}</p>
        </div>
      </div>

      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1.5">Patient-by-patient assignment ({data.total} third-trimester)</p>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {data.assignments.map((a) => (
          <div key={a.label} className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center gap-1.5 mb-0.5"><span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: a.color }} /><p className="text-[15px] font-bold leading-none" style={{ color: a.color }}>{a.count}</p></div>
            <p className="text-[9.5px] font-semibold text-gray-700">{a.label}</p>
            <p className="text-[8.5px] text-gray-400 leading-tight mt-0.5">{a.note}</p>
          </div>
        ))}
      </div>
      <p className="text-[9px] text-gray-400 leading-snug">{data.note}</p>
    </motion.div>
  );
}
