import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';

function Sparkline({ pts }) {
  const w = 88, h = 24, min = Math.min(...pts), max = Math.max(...pts), span = max - min || 1;
  const d = pts.map((p, i) => `${(i / (pts.length - 1)) * w},${h - ((p - min) / span) * (h - 4) - 2}`).join(' ');
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={d} fill="none" stroke="#DC2626" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={w} cy={h - ((pts[pts.length - 1] - min) / span) * (h - 4) - 2} r="2.4" fill="#DC2626" />
    </svg>
  );
}

// The original static card, kept as the offline fallback.
const STATIC_PATIENTS = [
  { id: 'P-2241', zip: '89820', dx: 'Preeclampsia', miles: 118, score: 94, missed: true, compound: 'HTN' },
  { id: 'P-2188', zip: '89820', dx: 'Prior preterm', miles: 118, score: 91, missed: true, compound: 'T2DM' },
  { id: 'P-2305', zip: '89445', dx: 'Gestational DM', miles: 109, score: 88, missed: true, compound: 'HTN' },
  { id: 'P-2150', zip: '89820', dx: 'Preeclampsia', miles: 118, score: 85, missed: true, compound: null },
  { id: 'P-2417', zip: '89438', dx: 'Gestational DM', miles: 132, score: 82, missed: true, compound: null },
  { id: 'P-2096', zip: '89445', dx: 'Prior preterm', miles: 109, score: 79, missed: true, compound: null },
];
const STATIC_DX = [{ label: 'Preeclampsia', count: 4 }, { label: 'Gestational DM', count: 3 }, { label: 'Prior preterm', count: 2 }];
const STATIC_BP = [
  { id: 'P-2241', pts: [128, 131, 134, 138, 142, 147] },
  { id: 'P-2188', pts: [122, 124, 129, 133, 136, 140] },
  { id: 'P-2305', pts: [130, 133, 135, 139, 144, 149] },
];

export function StaticMaternalRiskStratification() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Third-Trimester Cohort — Composite Risk Ranking</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">14 patients</span>
      </div>
      <div className="space-y-1.5 mb-3">
        {STATIC_PATIENTS.map((p) => (
          <div key={p.id} className="bg-white rounded-lg border border-gray-100 px-2.5 py-1.5 flex items-center gap-2">
            <span className="text-[10px] font-bold text-gray-700 w-12 flex-shrink-0">{p.id}</span>
            <span className="text-[9px] text-gray-400 w-10 flex-shrink-0">{p.zip}</span>
            <span className="text-[9.5px] text-gray-600 flex-1 truncate">{p.dx}</span>
            {p.compound && <span className="text-[8px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-1 py-0.5 rounded flex-shrink-0">+{p.compound}</span>}
            {p.missed && <span className="text-[8px] font-bold text-red-600 bg-red-50 px-1 py-0.5 rounded flex-shrink-0">missed visit</span>}
            <span className="text-[9px] text-gray-400 w-10 text-right flex-shrink-0">{p.miles} mi</span>
            <div className="w-16 h-2 rounded-full bg-gray-200 overflow-hidden flex-shrink-0">
              <div className="h-full rounded-full" style={{ width: `${p.score}%`, backgroundColor: RAIN_NAVY }} />
            </div>
            <span className="text-[10px] font-bold w-6 text-right flex-shrink-0" style={{ color: RAIN_NAVY }}>{p.score}</span>
          </div>
        ))}
        <p className="text-[9px] text-gray-400 pl-1">Showing 6 of 14 · 9 carry high-risk diagnoses · 6 have a missed visit since March 1</p>
      </div>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {STATIC_DX.map((d) => (
          <div key={d.label} className="bg-white rounded-lg p-2 border border-gray-100 text-center">
            <p className="text-[15px] font-bold" style={{ color: RAIN_NAVY }}>{d.count}</p>
            <p className="text-[9px] text-gray-500 leading-tight mt-0.5">{d.label}</p>
          </div>
        ))}
      </div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1.5">RPM blood-pressure trend — 3 compounding-risk patients</p>
      <div className="grid grid-cols-3 gap-2">
        {STATIC_BP.map((s) => (
          <div key={s.id} className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-bold text-gray-600">{s.id}</span>
              <span className="text-[9px] font-bold text-red-600">{s.pts[s.pts.length - 1]}<span className="text-gray-400 font-normal"> sys</span></span>
            </div>
            <Sparkline pts={s.pts} />
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// Live: all 14 real patients from the backend, same ranking as Maria's
// action package. Corrects the static card's per-patient distance (real
// value is a constant 115mi, not a 109-132 spread) and composite score
// (replaced with the real 0-5 risk-factor count); shows real BP trends for
// the 2 of 3 compounding patients who actually have RPM data, with the
// third explicitly marked as having none -- see maria_risk_stratification.py.
export default function MaternalRiskStratification() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('MaternalRiskStratification', 'maria')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticMaternalRiskStratification />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Ranking the third-trimester cohort…</div>;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Third-Trimester Cohort — Risk Factor Ranking</p>
        <span className="text-[10px] font-semibold text-red-600 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded">{data.total} patients</span>
      </div>
      <div className="space-y-1.5 mb-3 max-h-[260px] overflow-y-auto pr-0.5">
        {data.patients.map((p) => (
          <div key={p.id} className="bg-white rounded-lg border border-gray-100 px-2.5 py-1.5 flex items-center gap-2">
            <span className="text-[10px] font-bold text-gray-700 w-16 flex-shrink-0">{p.id}</span>
            <span className="text-[9px] text-gray-400 w-10 flex-shrink-0">{p.zip}</span>
            <span className="text-[9.5px] text-gray-600 flex-1 truncate">{p.dx || 'No registry dx'}</span>
            {p.compound && <span className="text-[8px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-1 py-0.5 rounded flex-shrink-0">+{p.compound}</span>}
            {p.missed && <span className="text-[8px] font-bold text-red-600 bg-red-50 px-1 py-0.5 rounded flex-shrink-0">missed visit</span>}
            <span className="text-[9px] text-gray-400 w-10 text-right flex-shrink-0">{p.miles} mi</span>
            <div className="w-16 h-2 rounded-full bg-gray-200 overflow-hidden flex-shrink-0">
              <div className="h-full rounded-full" style={{ width: `${(p.score / p.score_max) * 100}%`, backgroundColor: RAIN_NAVY }} />
            </div>
            <span className="text-[10px] font-bold w-8 text-right flex-shrink-0" style={{ color: RAIN_NAVY }}>{p.score}/{p.score_max}</span>
          </div>
        ))}
      </div>
      <p className="text-[9px] text-gray-400 pl-1 mb-2">
        All {data.total} shown · {data.dx_total} carry a high-risk diagnosis · {data.missed_total} have a missed visit since March 1
      </p>
      <div className="grid grid-cols-3 gap-2 mb-3">
        {data.dx_breakdown.map((d) => (
          <div key={d.label} className="bg-white rounded-lg p-2 border border-gray-100 text-center">
            <p className="text-[15px] font-bold" style={{ color: RAIN_NAVY }}>{d.count}</p>
            <p className="text-[9px] text-gray-500 leading-tight mt-0.5">{d.label}</p>
          </div>
        ))}
      </div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1.5">RPM blood-pressure trend — compounding-risk patients</p>
      <div className="grid grid-cols-3 gap-2">
        {data.bp_series.map((s) => (
          <div key={s.id} className="bg-white rounded-lg p-2 border border-gray-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-bold text-gray-600">{s.id}</span>
              <span className="text-[9px] font-bold text-red-600">{s.pts[s.pts.length - 1]}<span className="text-gray-400 font-normal"> sys</span></span>
            </div>
            <Sparkline pts={s.pts} />
          </div>
        ))}
        {data.no_rpm_compounding.map((id) => (
          <div key={id} className="bg-white rounded-lg p-2 border border-gray-100 flex flex-col items-center justify-center">
            <span className="text-[9px] font-bold text-gray-600">{id}</span>
            <span className="text-[8.5px] text-gray-400 text-center mt-1">No RPM data on file</span>
          </div>
        ))}
      </div>
      <p className="text-[9px] text-gray-400 mt-2 leading-snug">{data.note}</p>
    </motion.div>
  );
}
