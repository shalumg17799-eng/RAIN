import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchGenericComponent } from '@/clients/rain/genericApi';

const RAIN_NAVY = '#003366';
const dot = { red: 'bg-red-500', yellow: 'bg-amber-500', green: 'bg-emerald-500' };

// The original static card, kept as the offline fallback -- shown only when
// the backend can't be reached, so the app keeps working exactly as before.
const STATIC_SOURCES = [
  { name: 'Clinical EHR', status: 'yellow', note: 'FHIR drift (new connector)' },
  { name: 'RPM Platform', status: 'red', note: '78% completeness' },
  { name: 'Claims', status: 'green', note: 'Healthy' },
  { name: 'State HIE', status: 'green', note: 'Healthy' },
  { name: 'Telehealth', status: 'green', note: 'Healthy' },
  { name: 'SDOH Data', status: 'green', note: 'Healthy' },
  { name: 'Provider Directory', status: 'red', note: '1,240 unresolved refs' },
  { name: 'Public Health Reg.', status: 'green', note: 'Healthy' },
];
const STATIC_STATS = [['94%', 'FHIR conformance'], ['3.2 hrs', 'Avg pipeline lag'], ['14.8K', 'In quarantine']];

export function StaticDataHealthBoard() {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Data Health — Connected Sources</p>
        <span className="text-[10px] font-semibold text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">11 sources</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5 mb-3">
        {STATIC_SOURCES.map((s) => (
          <div key={s.name} className="bg-white rounded-lg border border-gray-100 px-2.5 py-1.5 flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dot[s.status]}`} />
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-semibold text-gray-700 truncate">{s.name}</p>
              <p className="text-[8.5px] text-gray-400 leading-tight truncate">{s.note}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {STATIC_STATS.map(([v, l]) => (
          <div key={l} className="bg-white rounded-lg p-2 border border-gray-100 text-center">
            <p className="text-[13px] font-bold" style={{ color: RAIN_NAVY }}>{v}</p>
            <p className="text-[8.5px] text-gray-500 leading-tight mt-0.5">{l}</p>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// Live: every source, status, and stat below comes from the backend, computed
// fresh from rain.db on each load (see david_data_health.py).
export default function DataHealthBoard() {
  const [data, setData] = useState(null);
  const [phase, setPhase] = useState('loading'); // loading | live | offline

  useEffect(() => {
    fetchGenericComponent('DataHealthBoard', 'david')
      .then((d) => { setData(d); setPhase('live'); })
      .catch(() => setPhase('offline'));
  }, []);

  if (phase === 'offline') return <StaticDataHealthBoard />;
  if (phase === 'loading' || !data) {
    return <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 text-[11px] text-gray-500">Loading data health from the source feeds…</div>;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className="bg-gray-50 rounded-xl p-4 border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-600">Data Health — Connected Sources</p>
        <span className="text-[10px] font-semibold text-gray-500 bg-white border border-gray-200 px-1.5 py-0.5 rounded">{data.source_count} sources</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5 mb-3">
        {data.sources.map((s) => (
          <div key={s.name} className="bg-white rounded-lg border border-gray-100 px-2.5 py-1.5 flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dot[s.status]}`} />
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-semibold text-gray-700 truncate">{s.name}</p>
              <p className="text-[8.5px] text-gray-400 leading-tight truncate">{s.note}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {data.stats.map((s) => (
          <div key={s.label} className="bg-white rounded-lg p-2 border border-gray-100 text-center">
            <p className="text-[13px] font-bold" style={{ color: RAIN_NAVY }}>{s.value}</p>
            <p className="text-[8.5px] text-gray-500 leading-tight mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
