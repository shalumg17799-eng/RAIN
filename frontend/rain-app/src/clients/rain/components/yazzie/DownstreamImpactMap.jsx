import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Baby, HeartPulse, Users } from 'lucide-react';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';
const ICONS = { 'Maternal risk engine': Baby, 'Chronic disease engine': HeartPulse, 'Population health engine': Users };

// The original static card, kept as the offline fallback.
const STATIC_ENGINES = [
  { icon: Baby, label: 'Maternal risk engine', detail: '6 high-risk prenatal patients lost attribution', owner: 'Dr. Delgado-Reyes' },
  { icon: HeartPulse, label: 'Chronic disease engine', detail: '41 diabetes + 5 CHF/COPD continuity flags dropped', owner: 'Sarah Whitehorse' },
  { icon: Users, label: 'Population health engine', detail: '64% continuity-loss ED attribution depends on this linkage', owner: 'Dr. Nair' },
];

export function StaticDownstreamImpactMap() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <p className="text-xs font-semibold text-gray-600 mb-3">Downstream Impact — Data Layer → Risk Engines</p>
      <div className="flex justify-center mb-3">
        <div className="px-3 py-1.5 rounded-lg text-white text-[10px] font-bold text-center" style={{ backgroundColor: RAIN_NAVY }}>1,240 unresolved provider references</div>
      </div>
      <div className="space-y-2 mb-3">
        {STATIC_ENGINES.map((e) => {
          const Icon = e.icon;
          return (
            <div key={e.label} className="bg-white rounded-lg border border-gray-100 p-2.5 flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${RAIN_NAVY}12` }}>
                <Icon className="w-3.5 h-3.5" style={{ color: RAIN_NAVY }} />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] font-semibold text-gray-800">{e.label}</p>
                  <span className="text-[8.5px] text-gray-400">{e.owner}</span>
                </div>
                <p className="text-[9.5px] text-gray-500 leading-tight mt-0.5">{e.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
      <div className="bg-white rounded-lg border border-gray-100 p-3">
        <p className="text-[9px] uppercase tracking-wider text-gray-400 font-semibold mb-1.5">Cohort completeness after reconciliation</p>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-3 rounded-full bg-gray-200 overflow-hidden relative">
            <div className="h-full rounded-full bg-red-300" style={{ width: '86%' }} />
            <div className="h-full rounded-full absolute top-0 left-0" style={{ width: '99%', backgroundColor: RAIN_NAVY, opacity: 0.18 }} />
          </div>
        </div>
        <div className="flex items-center justify-between mt-1 text-[10px]">
          <span className="text-red-500 font-semibold">86% now</span>
          <span className="font-bold" style={{ color: RAIN_NAVY }}>→ 99% within one ingestion cycle</span>
        </div>
      </div>
    </motion.div>
  );
}

// Live: the maternal-engine claim is corrected from the scripted "6
// high-risk prenatal patients" to the real 0 (every affected pregnancy
// episode was already reassigned), the chronic breakdown now includes the
// 2 hypertension patients the static card omitted, and the fabricated
// 86%->99% completeness bar is dropped -- see david_downstream_impact.py.
export default function DownstreamImpactMap() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading');

  useEffect(() => {
    fetchGenericComponent('DownstreamImpact', 'david')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticDownstreamImpactMap />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Tracing the downstream impact…</div>;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <p className="text-xs font-semibold text-gray-600 mb-3">Downstream Impact — Data Layer → Risk Engines</p>
      <div className="flex justify-center mb-3">
        <div className="px-3 py-1.5 rounded-lg text-white text-[10px] font-bold text-center" style={{ backgroundColor: RAIN_NAVY }}>{data.unresolved_refs.toLocaleString()} unresolved provider references</div>
      </div>
      <div className="space-y-2 mb-3">
        {data.engines.map((e) => {
          const Icon = ICONS[e.label] || Users;
          return (
            <div key={e.label} className="bg-white rounded-lg border border-gray-100 p-2.5 flex items-start gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${RAIN_NAVY}12` }}>
                <Icon className="w-3.5 h-3.5" style={{ color: RAIN_NAVY }} />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] font-semibold text-gray-800">{e.label}</p>
                  <span className="text-[8.5px] text-gray-400">{e.owner}</span>
                </div>
                <p className="text-[9.5px] text-gray-500 leading-tight mt-0.5">{e.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[9px] text-gray-400 leading-snug">{data.note}</p>
    </motion.div>
  );
}
